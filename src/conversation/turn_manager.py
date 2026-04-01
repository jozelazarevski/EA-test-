"""
Turn Manager — Manages conversation turns between the simulator and the EA chatbot.

Handles:
- Max-turns cutoff
- Timeout per turn (30s default)
- Retry on API failure (3x exponential backoff)
- Conversation termination detection (resolution, escalation, give-up)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


class TerminationReason(str, Enum):
    """Why a conversation ended."""
    MAX_TURNS = "max_turns"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    GAVE_UP = "gave_up"
    TIMEOUT = "timeout"
    API_FAILURE = "api_failure"
    EA_ERROR = "ea_error"


@dataclass
class Turn:
    """A single conversation turn."""
    turn_number: int
    speaker: str  # "technician" or "advisor"
    message: str
    response_time: float = 0.0
    pdf_links: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


# Type alias for the callback that sends a message to the EA chatbot.
# Signature: async (question: str) -> dict  (same shape as agent.send_question)
EASendFn = Callable[[str], Awaitable[dict[str, Any]]]


class TurnManager:
    """Orchestrates individual turns between the persona simulator and the EA chatbot."""

    def __init__(
        self,
        *,
        max_turns: int = 20,
        turn_timeout: float = 30.0,
        max_retries: int = 3,
        model: str | None = None,
    ) -> None:
        self.max_turns = max_turns
        self.turn_timeout = turn_timeout
        self.max_retries = max_retries
        self.model = model or LLM_MODEL
        self._client: anthropic.Anthropic | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_conversation(
        self,
        system_prompt: str,
        opening_user_prompt: str,
        ea_send_fn: EASendFn,
        follow_up_prompt_fn: Callable[[str], str],
    ) -> tuple[list[Turn], TerminationReason]:
        """
        Run a full conversation loop.

        Args:
            system_prompt: The persona system prompt (from PersonaEngine).
            opening_user_prompt: Prompt for Claude to produce the first message.
            ea_send_fn: Async callable that sends a message to the EA chatbot
                        and returns a response dict (like agent.send_question).
            follow_up_prompt_fn: Callable that takes the advisor's last reply
                                 and returns a user-message prompt for Claude
                                 to produce the next technician message.

        Returns:
            (turns, termination_reason)
        """
        turns: list[Turn] = []
        claude_messages: list[dict[str, str]] = []
        turn_number = 0

        # -- Step 1: Generate the technician's opening message ---------------
        tech_message, reason = await self._generate_tech_message(
            system_prompt,
            claude_messages,
            opening_user_prompt,
            turn_number,
        )
        if reason is not None:
            return turns, reason

        turn_number += 1
        turns.append(Turn(
            turn_number=turn_number,
            speaker="technician",
            message=tech_message,
        ))
        # Track messages for Claude context
        claude_messages.append({"role": "user", "content": opening_user_prompt})
        claude_messages.append({"role": "assistant", "content": tech_message})

        # -- Step 2: Conversation loop ----------------------------------------
        while turn_number < self.max_turns:
            # 2a. Send technician message to EA chatbot
            ea_result, ea_error = await self._send_to_ea(ea_send_fn, tech_message)
            turn_number += 1

            if ea_error:
                turns.append(Turn(
                    turn_number=turn_number,
                    speaker="advisor",
                    message="",
                    error=ea_error,
                ))
                return turns, TerminationReason.EA_ERROR

            advisor_reply = ea_result.get("response_text", "")
            turns.append(Turn(
                turn_number=turn_number,
                speaker="advisor",
                message=advisor_reply,
                response_time=ea_result.get("response_time", 0.0),
                pdf_links=ea_result.get("pdf_links", []),
            ))

            # 2b. Check if we've hit max turns
            if turn_number >= self.max_turns:
                return turns, TerminationReason.MAX_TURNS

            # 2c. Generate technician follow-up
            follow_up_user_prompt = follow_up_prompt_fn(advisor_reply)
            tech_message, reason = await self._generate_tech_message(
                system_prompt,
                claude_messages,
                follow_up_user_prompt,
                turn_number,
            )
            if reason is not None:
                return turns, reason

            turn_number += 1
            turns.append(Turn(
                turn_number=turn_number,
                speaker="technician",
                message=tech_message,
            ))
            claude_messages.append({"role": "user", "content": follow_up_user_prompt})
            claude_messages.append({"role": "assistant", "content": tech_message})

            # 2d. Check for natural termination
            termination = self._detect_termination(tech_message)
            if termination is not None:
                return turns, termination

        return turns, TerminationReason.MAX_TURNS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not ANTHROPIC_API_KEY:
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY is required. "
                    "Set it in .env or export ANTHROPIC_API_KEY='your-key-here'"
                )
            self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._client

    async def _generate_tech_message(
        self,
        system_prompt: str,
        prior_messages: list[dict[str, str]],
        user_prompt: str,
        turn_number: int,
    ) -> tuple[str, TerminationReason | None]:
        """
        Call Claude API to generate the technician's next message.

        Returns:
            (message_text, termination_reason_or_None)
        """
        messages = prior_messages + [{"role": "user", "content": user_prompt}]

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                text = await asyncio.wait_for(
                    self._call_claude(system_prompt, messages),
                    timeout=self.turn_timeout,
                )
                return text, None
            except asyncio.TimeoutError:
                logger.warning(
                    "Turn %d: Claude API timeout (attempt %d/%d)",
                    turn_number, attempt + 1, self.max_retries,
                )
                last_error = TimeoutError("Claude API call timed out")
            except anthropic.APIError as exc:
                logger.warning(
                    "Turn %d: Claude API error (attempt %d/%d): %s",
                    turn_number, attempt + 1, self.max_retries, exc,
                )
                last_error = exc

            if attempt < self.max_retries - 1:
                backoff = 2 ** (attempt + 1)
                await asyncio.sleep(backoff)

        logger.error("Turn %d: all retries exhausted — %s", turn_number, last_error)
        if isinstance(last_error, TimeoutError):
            return "", TerminationReason.TIMEOUT
        return "", TerminationReason.API_FAILURE

    async def _call_claude(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Make a single Claude API call (runs sync client in a thread)."""
        client = self._get_client()

        def _sync_call() -> str:
            response = client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text.strip()

        return await asyncio.get_event_loop().run_in_executor(None, _sync_call)

    async def _send_to_ea(
        self,
        ea_send_fn: EASendFn,
        message: str,
    ) -> tuple[dict[str, Any], str | None]:
        """
        Send a message to the EA chatbot with timeout.

        Returns:
            (result_dict, error_string_or_None)
        """
        try:
            result = await asyncio.wait_for(
                ea_send_fn(message),
                timeout=self.turn_timeout * 4,  # EA can be slow
            )
            if result.get("error"):
                return result, result["error"]
            return result, None
        except asyncio.TimeoutError:
            return {}, f"EA chatbot did not respond within {self.turn_timeout * 4}s"
        except Exception as exc:
            return {}, f"EA send error: {exc}"

    @staticmethod
    def _detect_termination(tech_message: str) -> TerminationReason | None:
        """
        Analyse the technician's message for signals that the conversation
        should end naturally.
        """
        lower = tech_message.lower()

        # Resolution signals
        resolution_phrases = [
            "that fixed it",
            "that solved it",
            "that worked",
            "problem is resolved",
            "issue is resolved",
            "running normally now",
            "back up and running",
            "thanks, that did it",
            "thank you, that resolved",
            "all good now",
            "that was the issue",
            "appreciate the help",
            "we're good here",
        ]
        if any(phrase in lower for phrase in resolution_phrases):
            return TerminationReason.RESOLVED

        # Escalation signals
        escalation_phrases = [
            "escalate",
            "call my supervisor",
            "need to get my manager",
            "going to call support",
            "opening a service ticket",
            "need on-site support",
            "sending this to engineering",
            "need a factory rep",
        ]
        if any(phrase in lower for phrase in escalation_phrases):
            return TerminationReason.ESCALATED

        # Give-up signals
        giveup_phrases = [
            "this isn't helping",
            "not getting anywhere",
            "going in circles",
            "i give up",
            "forget it",
            "never mind",
            "not useful",
            "waste of time",
        ]
        if any(phrase in lower for phrase in giveup_phrases):
            return TerminationReason.GAVE_UP

        return None

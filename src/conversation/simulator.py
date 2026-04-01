"""
Conversation Simulator — Orchestrates a full simulated conversation.

Input: scenario + persona.
Output: ConversationLog dataclass with all turns, metadata, and termination reason.

Uses PersonaEngine for prompt construction and TurnManager for sequencing.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

from src.conversation.persona_engine import PersonaEngine
from src.conversation.turn_manager import TurnManager, Turn, TerminationReason

logger = logging.getLogger(__name__)

# Type alias matching agent.send_question signature
EASendFn = Callable[[str], Awaitable[dict[str, Any]]]


@dataclass
class ConversationLog:
    """Complete record of a simulated conversation."""

    # Identifiers
    scenario_id: str
    persona_id: str

    # Inputs (stored for reproducibility)
    scenario: dict[str, Any]
    persona: dict[str, Any]
    system_prompt: str

    # Conversation data
    turns: list[Turn] = field(default_factory=list)
    termination_reason: TerminationReason = TerminationReason.MAX_TURNS

    # Timing
    started_at: float = 0.0
    finished_at: float = 0.0

    # Metadata
    model: str = ""
    max_turns: int = 0
    turn_timeout: float = 0.0

    @property
    def duration(self) -> float:
        """Total wall-clock time in seconds."""
        return round(self.finished_at - self.started_at, 2)

    @property
    def num_turns(self) -> int:
        return len(self.turns)

    @property
    def technician_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.speaker == "technician"]

    @property
    def advisor_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.speaker == "advisor"]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "scenario_id": self.scenario_id,
            "persona_id": self.persona_id,
            "scenario": self.scenario,
            "persona": self.persona,
            "system_prompt": self.system_prompt,
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "speaker": t.speaker,
                    "message": t.message,
                    "response_time": t.response_time,
                    "pdf_links": t.pdf_links,
                    "error": t.error,
                    "timestamp": t.timestamp,
                }
                for t in self.turns
            ],
            "termination_reason": self.termination_reason.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration": self.duration,
            "num_turns": self.num_turns,
            "model": self.model,
            "max_turns": self.max_turns,
            "turn_timeout": self.turn_timeout,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Save the conversation log to a JSON file.

        If *path* is a directory, a filename is auto-generated from the
        scenario and persona IDs.

        Returns:
            The Path actually written.
        """
        path = Path(path)
        if path.is_dir():
            filename = f"conversation_{self.scenario_id}_{self.persona_id}_{int(self.started_at)}.json"
            path = path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info("Saved conversation log to %s", path)
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationLog":
        """Reconstruct a ConversationLog from a dict (e.g. loaded from JSON)."""
        turns = [
            Turn(
                turn_number=t["turn_number"],
                speaker=t["speaker"],
                message=t["message"],
                response_time=t.get("response_time", 0.0),
                pdf_links=t.get("pdf_links", []),
                error=t.get("error"),
                timestamp=t.get("timestamp", 0.0),
            )
            for t in data.get("turns", [])
        ]
        return cls(
            scenario_id=data["scenario_id"],
            persona_id=data["persona_id"],
            scenario=data.get("scenario", {}),
            persona=data.get("persona", {}),
            system_prompt=data.get("system_prompt", ""),
            turns=turns,
            termination_reason=TerminationReason(data.get("termination_reason", "max_turns")),
            started_at=data.get("started_at", 0.0),
            finished_at=data.get("finished_at", 0.0),
            model=data.get("model", ""),
            max_turns=data.get("max_turns", 0),
            turn_timeout=data.get("turn_timeout", 0.0),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ConversationLog":
        """Load a ConversationLog from a JSON file."""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


class ConversationSimulator:
    """
    High-level orchestrator: runs a single simulated conversation between
    a technician persona (via Claude API) and the EA chatbot.
    """

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
        self.model = model

        self._persona_engine = PersonaEngine()
        self._turn_manager = TurnManager(
            max_turns=max_turns,
            turn_timeout=turn_timeout,
            max_retries=max_retries,
            model=model,
        )

    async def run(
        self,
        scenario: dict[str, Any],
        persona: dict[str, Any],
        ea_send_fn: EASendFn,
    ) -> ConversationLog:
        """
        Execute a full simulated conversation.

        Args:
            scenario: Scenario definition dict. Expected keys:
                      id, title, equipment, symptoms (list[str]), context.
                      May contain root_cause — it will NOT be exposed to the persona.
            persona: Persona definition dict (same shape as personas.py entries).
            ea_send_fn: Async callable matching agent.send_question's signature.

        Returns:
            ConversationLog with all turns, metadata, and termination reason.
        """
        scenario_id = scenario.get("id", "unknown")
        persona_id = persona.get("id", "unknown")
        logger.info(
            "Starting conversation: scenario=%s persona=%s",
            scenario_id, persona_id,
        )

        # Reset emotional state for a fresh conversation
        self._persona_engine.reset_state()

        # Build the system prompt (no evaluation criteria, no root cause)
        system_prompt = self._persona_engine.build_system_prompt(persona, scenario)

        # Build the opening user prompt
        opening_prompt = self._persona_engine.build_opening_message_prompt(
            persona, scenario,
        )

        started_at = time.time()

        turns, termination_reason = await self._turn_manager.run_conversation(
            system_prompt=system_prompt,
            opening_user_prompt=opening_prompt,
            ea_send_fn=ea_send_fn,
            follow_up_prompt_fn=self._persona_engine.build_follow_up_prompt,
        )

        finished_at = time.time()

        log = ConversationLog(
            scenario_id=scenario_id,
            persona_id=persona_id,
            scenario=scenario,
            persona=persona,
            system_prompt=system_prompt,
            turns=turns,
            termination_reason=termination_reason,
            started_at=started_at,
            finished_at=finished_at,
            model=self._turn_manager.model,
            max_turns=self.max_turns,
            turn_timeout=self.turn_timeout,
        )

        logger.info(
            "Conversation complete: scenario=%s persona=%s turns=%d reason=%s duration=%.1fs",
            scenario_id, persona_id, log.num_turns,
            termination_reason.value, log.duration,
        )

        return log

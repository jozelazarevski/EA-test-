"""
Batch Runner — Executes scenario x persona conversation matrix.

Runs multiple simulated conversations with concurrency control, progress
callbacks, automatic JSON persistence, and aggregate statistics.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

from src.conversation.simulator import ConversationSimulator, ConversationLog
from src.conversation.turn_manager import TerminationReason

logger = logging.getLogger(__name__)

# Type alias matching agent.send_question signature
EASendFn = Callable[[str], Awaitable[dict[str, Any]]]

# Progress callback: (completed, total, latest_log)
ProgressFn = Callable[[int, int, ConversationLog], None]


@dataclass
class BatchStats:
    """Aggregate statistics across a batch of conversations."""

    total: int = 0
    completed: int = 0
    failed: int = 0

    # Termination breakdown
    termination_counts: dict[str, int] = field(default_factory=dict)

    # Timing
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0

    # Turn stats
    total_turns: int = 0
    avg_turns: float = 0.0
    min_turns: int = 999
    max_turns: int = 0

    # Resolution rate
    resolved_count: int = 0
    escalated_count: int = 0
    gave_up_count: int = 0

    @property
    def resolution_rate(self) -> float:
        """Percentage of conversations that ended in resolution."""
        return (self.resolved_count / self.completed * 100) if self.completed else 0.0

    @property
    def escalation_rate(self) -> float:
        return (self.escalated_count / self.completed * 100) if self.completed else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "termination_counts": self.termination_counts,
            "resolution_rate_pct": round(self.resolution_rate, 1),
            "escalation_rate_pct": round(self.escalation_rate, 1),
            "timing": {
                "total_duration_s": round(self.total_duration, 2),
                "avg_duration_s": round(self.avg_duration, 2),
                "min_duration_s": round(self.min_duration, 2),
                "max_duration_s": round(self.max_duration, 2),
            },
            "turns": {
                "total": self.total_turns,
                "avg": round(self.avg_turns, 1),
                "min": self.min_turns if self.min_turns < 999 else 0,
                "max": self.max_turns,
            },
        }


@dataclass
class BatchResult:
    """Complete result of a batch run."""

    logs: list[ConversationLog] = field(default_factory=list)
    stats: BatchStats = field(default_factory=BatchStats)
    started_at: float = 0.0
    finished_at: float = 0.0
    output_dir: str = ""

    @property
    def wall_clock_time(self) -> float:
        return round(self.finished_at - self.started_at, 2)


class BatchRunner:
    """Run a matrix of scenario x persona conversations with concurrency control."""

    def __init__(
        self,
        *,
        max_concurrency: int = 3,
        max_turns: int = 20,
        turn_timeout: float = 30.0,
        max_retries: int = 3,
        model: str | None = None,
        output_dir: str | Path | None = None,
        progress_fn: ProgressFn | None = None,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.max_turns = max_turns
        self.turn_timeout = turn_timeout
        self.max_retries = max_retries
        self.model = model
        self.output_dir = Path(output_dir) if output_dir else None
        self.progress_fn = progress_fn

    async def run(
        self,
        scenarios: list[dict[str, Any]],
        personas: list[dict[str, Any]],
        ea_send_fn_factory: Callable[[], Awaitable[EASendFn]],
    ) -> BatchResult:
        """
        Execute all scenario x persona combinations.

        Args:
            scenarios: List of scenario dicts.
            personas: List of persona dicts.
            ea_send_fn_factory: Async factory that returns a new EASendFn
                                for each conversation (to isolate browser
                                sessions if needed). If you want to share a
                                single session, have the factory return the
                                same function each time.

        Returns:
            BatchResult with all logs and aggregate statistics.
        """
        # Build the work matrix
        pairs = [
            (scenario, persona)
            for scenario in scenarios
            for persona in personas
        ]
        total = len(pairs)
        logger.info("Batch run: %d conversations (%d scenarios x %d personas)",
                     total, len(scenarios), len(personas))

        result = BatchResult(started_at=time.time())
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            result.output_dir = str(self.output_dir)

        semaphore = asyncio.Semaphore(self.max_concurrency)
        completed = 0
        lock = asyncio.Lock()

        async def _run_one(scenario: dict, persona: dict) -> ConversationLog | None:
            nonlocal completed
            async with semaphore:
                sim = ConversationSimulator(
                    max_turns=self.max_turns,
                    turn_timeout=self.turn_timeout,
                    max_retries=self.max_retries,
                    model=self.model,
                )
                try:
                    ea_send_fn = await ea_send_fn_factory()
                    log = await sim.run(scenario, persona, ea_send_fn)
                except Exception as exc:
                    logger.error(
                        "Conversation failed: scenario=%s persona=%s error=%s",
                        scenario.get("id"), persona.get("id"), exc,
                    )
                    # Create a minimal failure log
                    log = ConversationLog(
                        scenario_id=scenario.get("id", "unknown"),
                        persona_id=persona.get("id", "unknown"),
                        scenario=scenario,
                        persona=persona,
                        system_prompt="",
                        termination_reason=TerminationReason.API_FAILURE,
                        started_at=time.time(),
                        finished_at=time.time(),
                    )

                # Persist immediately
                if self.output_dir:
                    try:
                        log.save(self.output_dir)
                    except Exception as exc:
                        logger.warning("Failed to save log: %s", exc)

                async with lock:
                    completed += 1
                    if self.progress_fn:
                        self.progress_fn(completed, total, log)

                return log

        # Run all conversations with concurrency limit
        tasks = [_run_one(s, p) for s, p in pairs]
        logs = await asyncio.gather(*tasks, return_exceptions=False)
        result.logs = [log for log in logs if log is not None]
        result.finished_at = time.time()

        # Compute stats
        result.stats = self._compute_stats(result.logs)
        result.stats.total = total

        logger.info(
            "Batch complete: %d/%d conversations in %.1fs — %.1f%% resolved",
            result.stats.completed, total, result.wall_clock_time,
            result.stats.resolution_rate,
        )

        return result

    @staticmethod
    def _compute_stats(logs: list[ConversationLog]) -> BatchStats:
        stats = BatchStats()
        stats.completed = len(logs)

        for log in logs:
            reason = log.termination_reason.value
            stats.termination_counts[reason] = stats.termination_counts.get(reason, 0) + 1

            duration = log.duration
            stats.total_duration += duration
            stats.min_duration = min(stats.min_duration, duration)
            stats.max_duration = max(stats.max_duration, duration)

            turns = log.num_turns
            stats.total_turns += turns
            stats.min_turns = min(stats.min_turns, turns)
            stats.max_turns = max(stats.max_turns, turns)

            if log.termination_reason == TerminationReason.RESOLVED:
                stats.resolved_count += 1
            elif log.termination_reason == TerminationReason.ESCALATED:
                stats.escalated_count += 1
            elif log.termination_reason == TerminationReason.GAVE_UP:
                stats.gave_up_count += 1
            elif log.termination_reason in (TerminationReason.API_FAILURE,
                                            TerminationReason.EA_ERROR):
                stats.failed += 1

        if stats.completed:
            stats.avg_duration = stats.total_duration / stats.completed
            stats.avg_turns = stats.total_turns / stats.completed

        return stats

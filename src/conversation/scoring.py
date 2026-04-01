"""
Multi-Tier Scoring Model — Replaces binary pass/fail with nuanced verdicts.

Features:
- 5 quality tiers (Exemplary → Critical Failure) instead of pass/fail
- Weighted dimension scoring (safety 2x, accuracy 1.5x, etc.)
- Structured reasoning chains explaining WHY a score was given
- Critical dimension auto-downgrades (e.g. safety < 4 caps overall tier)
- Conversation-level trajectory analysis (improving / stable / degrading)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Quality Tiers
# ---------------------------------------------------------------------------

class QualityTier(str, Enum):
    """Five-level quality classification replacing binary pass/fail."""
    EXEMPLARY = "exemplary"           # 9-10
    PROFICIENT = "proficient"         # 7-8.99
    DEVELOPING = "developing"         # 5-6.99
    UNSATISFACTORY = "unsatisfactory" # 3-4.99
    CRITICAL_FAILURE = "critical_failure"  # 1-2.99

    @property
    def label(self) -> str:
        return {
            "exemplary": "Exemplary",
            "proficient": "Proficient",
            "developing": "Developing",
            "unsatisfactory": "Unsatisfactory",
            "critical_failure": "Critical Failure",
        }[self.value]

    @property
    def color(self) -> str:
        return {
            "exemplary": "#276749",      # dark green
            "proficient": "#38a169",     # green
            "developing": "#d69e2e",     # amber
            "unsatisfactory": "#dd6b20", # orange
            "critical_failure": "#c53030",  # red
        }[self.value]

    @property
    def bg_color(self) -> str:
        return {
            "exemplary": "#c6f6d5",
            "proficient": "#e6ffed",
            "developing": "#fefcbf",
            "unsatisfactory": "#feebc8",
            "critical_failure": "#fed7d7",
        }[self.value]

    @property
    def icon(self) -> str:
        return {
            "exemplary": "★★",
            "proficient": "★",
            "developing": "◐",
            "unsatisfactory": "▽",
            "critical_failure": "✖",
        }[self.value]


def tier_from_score(score: float) -> QualityTier:
    """Map a 1-10 score to a quality tier."""
    if score >= 9.0:
        return QualityTier.EXEMPLARY
    elif score >= 7.0:
        return QualityTier.PROFICIENT
    elif score >= 5.0:
        return QualityTier.DEVELOPING
    elif score >= 3.0:
        return QualityTier.UNSATISFACTORY
    else:
        return QualityTier.CRITICAL_FAILURE


# ---------------------------------------------------------------------------
# Dimension Weights
# ---------------------------------------------------------------------------

# Weights reflect the relative importance of each evaluation dimension.
# Safety and accuracy failures are more consequential than style issues.
DIMENSION_WEIGHTS: dict[str, float] = {
    "safety":       2.0,   # Critical — bad safety advice is dangerous
    "accuracy":     1.5,   # High — wrong information erodes trust
    "completeness": 1.2,   # Medium-high — partial answers waste time
    "relevance":    1.0,   # Standard
    "clarity":      0.8,   # Lower — style matters less than substance
    "persona_fit":  0.8,   # Lower — nice-to-have vs need-to-have
}

# Dimensions where a low score auto-caps the overall tier
CRITICAL_DIMENSIONS: dict[str, QualityTier] = {
    "safety":   QualityTier.UNSATISFACTORY,   # safety < 4 → cap at UNSATISFACTORY
    "accuracy": QualityTier.DEVELOPING,       # accuracy < 4 → cap at DEVELOPING
}
CRITICAL_THRESHOLD = 4.0


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------

@dataclass
class DimensionResult:
    """Scored result for a single evaluation dimension."""
    name: str
    raw_score: float        # 1-10 from the LLM evaluator
    weight: float
    weighted_score: float   # raw_score * weight
    tier: QualityTier
    feedback: str
    is_critical_fail: bool = False


@dataclass
class ScoringResult:
    """Complete scored evaluation with reasoning."""
    # Scores
    raw_score: float              # Simple average of dimension scores (1-10)
    weighted_score: float         # Weighted average normalised to 1-10
    tier: QualityTier
    tier_before_caps: QualityTier  # Tier before critical-dimension caps applied

    # Dimensions
    dimensions: list[DimensionResult] = field(default_factory=list)

    # Reasoning
    reasoning: list[str] = field(default_factory=list)
    verdict: str = ""
    critical_flags: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_score": round(self.raw_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "tier": self.tier.value,
            "tier_label": self.tier.label,
            "tier_color": self.tier.color,
            "tier_before_caps": self.tier_before_caps.value,
            "dimensions": [
                {
                    "name": d.name,
                    "raw_score": d.raw_score,
                    "weight": d.weight,
                    "weighted_score": round(d.weighted_score, 2),
                    "tier": d.tier.value,
                    "feedback": d.feedback,
                    "is_critical_fail": d.is_critical_fail,
                }
                for d in self.dimensions
            ],
            "reasoning": self.reasoning,
            "verdict": self.verdict,
            "critical_flags": self.critical_flags,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


def score_evaluation(eval_data: dict[str, Any]) -> ScoringResult:
    """
    Take a raw LLM evaluation dict and produce a full ScoringResult
    with weighted scores, tier classification, and reasoning chain.

    Args:
        eval_data: Dict from llm_evaluator.evaluate_response() with
                   'dimensions', 'strengths', 'weaknesses', 'red_flags', 'summary'.

    Returns:
        ScoringResult with all scoring, tier, and reasoning data.
    """
    dimensions_raw = eval_data.get("dimensions", {})
    reasoning: list[str] = []
    critical_flags: list[str] = []
    dim_results: list[DimensionResult] = []

    total_weighted = 0.0
    total_weight = 0.0
    total_raw = 0.0
    dim_count = 0

    for dim_name, weight in DIMENSION_WEIGHTS.items():
        dim_data = dimensions_raw.get(dim_name, {})
        raw_score = float(dim_data.get("score", 0))
        feedback = dim_data.get("feedback", "")

        weighted = raw_score * weight
        total_weighted += weighted
        total_weight += weight
        total_raw += raw_score
        dim_count += 1

        dim_tier = tier_from_score(raw_score)

        # Check for critical dimension failure
        is_critical = False
        if dim_name in CRITICAL_DIMENSIONS and raw_score < CRITICAL_THRESHOLD:
            is_critical = True
            critical_flags.append(
                f"{dim_name.title()} scored {raw_score}/10 (below {CRITICAL_THRESHOLD} threshold) — "
                f"this caps the overall tier at {CRITICAL_DIMENSIONS[dim_name].label}"
            )

        dim_results.append(DimensionResult(
            name=dim_name,
            raw_score=raw_score,
            weight=weight,
            weighted_score=weighted,
            tier=dim_tier,
            feedback=feedback,
            is_critical_fail=is_critical,
        ))

    # Compute overall scores
    raw_avg = total_raw / dim_count if dim_count else 0.0
    weighted_avg = total_weighted / total_weight if total_weight else 0.0

    # Determine tier from weighted score
    tier_before_caps = tier_from_score(weighted_avg)
    final_tier = tier_before_caps

    # Apply critical dimension caps
    for dim_name, cap_tier in CRITICAL_DIMENSIONS.items():
        dim_data = dimensions_raw.get(dim_name, {})
        raw_score = float(dim_data.get("score", 0))
        if raw_score < CRITICAL_THRESHOLD:
            # Cap: final_tier cannot be better than cap_tier
            tier_order = list(QualityTier)
            if tier_order.index(final_tier) < tier_order.index(cap_tier):
                reasoning.append(
                    f"Overall tier downgraded from {final_tier.label} to "
                    f"{cap_tier.label} because {dim_name} scored {raw_score}/10 "
                    f"(critical threshold: {CRITICAL_THRESHOLD})"
                )
                final_tier = cap_tier

    # Build reasoning chain
    # Sort dimensions by score to highlight best/worst
    sorted_dims = sorted(dim_results, key=lambda d: d.raw_score)
    worst = sorted_dims[0] if sorted_dims else None
    best = sorted_dims[-1] if sorted_dims else None

    if best and worst:
        reasoning.insert(0,
            f"Strongest dimension: {best.name} ({best.raw_score}/10, weight {best.weight}x)"
        )
        reasoning.insert(1,
            f"Weakest dimension: {worst.name} ({worst.raw_score}/10, weight {worst.weight}x)"
        )

    reasoning.append(
        f"Raw average: {raw_avg:.1f}/10 → Weighted average: {weighted_avg:.1f}/10"
    )

    if tier_before_caps != final_tier:
        reasoning.append(
            f"Tier adjusted: {tier_before_caps.label} → {final_tier.label} "
            f"(due to critical dimension failures)"
        )
    else:
        reasoning.append(f"Quality tier: {final_tier.label} ({final_tier.icon})")

    # Red flags from original evaluation
    red_flags = eval_data.get("red_flags", [])
    if red_flags:
        for flag in red_flags:
            critical_flags.append(f"Red flag: {flag}")
        reasoning.append(
            f"{len(red_flags)} red flag(s) detected — review required"
        )

    # Build verdict
    verdict = _build_verdict(final_tier, weighted_avg, dim_results, critical_flags, eval_data)

    return ScoringResult(
        raw_score=raw_avg,
        weighted_score=weighted_avg,
        tier=final_tier,
        tier_before_caps=tier_before_caps,
        dimensions=dim_results,
        reasoning=reasoning,
        verdict=verdict,
        critical_flags=critical_flags,
        strengths=eval_data.get("strengths", []),
        weaknesses=eval_data.get("weaknesses", []),
    )


def _build_verdict(
    tier: QualityTier,
    score: float,
    dims: list[DimensionResult],
    critical_flags: list[str],
    eval_data: dict[str, Any],
) -> str:
    """Generate a human-readable verdict paragraph with clear reasoning."""
    parts: list[str] = []

    # Opening — overall assessment
    tier_descriptions = {
        QualityTier.EXEMPLARY: (
            f"This response scored {score:.1f}/10 (weighted) and is classified as Exemplary. "
            "It exceeds expectations across all measured dimensions."
        ),
        QualityTier.PROFICIENT: (
            f"This response scored {score:.1f}/10 (weighted) and is classified as Proficient. "
            "It meets expectations and provides solid, actionable guidance."
        ),
        QualityTier.DEVELOPING: (
            f"This response scored {score:.1f}/10 (weighted) and is classified as Developing. "
            "It partially addresses the question but has notable gaps."
        ),
        QualityTier.UNSATISFACTORY: (
            f"This response scored {score:.1f}/10 (weighted) and is classified as Unsatisfactory. "
            "It falls significantly short of expectations."
        ),
        QualityTier.CRITICAL_FAILURE: (
            f"This response scored {score:.1f}/10 (weighted) and is classified as a Critical Failure. "
            "It contains dangerous, incorrect, or wholly inadequate content."
        ),
    }
    parts.append(tier_descriptions[tier])

    # Highlight the key driver
    if dims:
        sorted_by_impact = sorted(dims, key=lambda d: d.weighted_score)
        worst = sorted_by_impact[0]
        best = sorted_by_impact[-1]

        if worst.raw_score < 5:
            parts.append(
                f"The primary concern is {worst.name} ({worst.raw_score}/10): "
                f"{worst.feedback}"
            )
        if best.raw_score >= 8 and best != worst:
            parts.append(
                f"A notable strength is {best.name} ({best.raw_score}/10): "
                f"{best.feedback}"
            )

    # Critical flags
    if critical_flags:
        parts.append(
            f"ATTENTION: {len(critical_flags)} critical issue(s) require review: "
            + "; ".join(critical_flags[:2])
        )

    # LLM summary as closing
    llm_summary = eval_data.get("summary", "")
    if llm_summary:
        parts.append(f"Evaluator notes: {llm_summary}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Conversation-Level Trajectory Analysis
# ---------------------------------------------------------------------------

class Trajectory(str, Enum):
    """How quality is changing across conversation turns."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"

    @property
    def color(self) -> str:
        return {
            "improving": "#38a169",
            "stable": "#3182ce",
            "degrading": "#e53e3e",
            "volatile": "#d69e2e",
            "insufficient_data": "#a0aec0",
        }[self.value]

    @property
    def icon(self) -> str:
        return {
            "improving": "↗",
            "stable": "→",
            "degrading": "↘",
            "volatile": "↕",
            "insufficient_data": "·",
        }[self.value]


@dataclass
class ConversationScore:
    """Aggregated scoring across an entire conversation."""
    turn_scores: list[ScoringResult]
    overall_weighted_score: float
    overall_tier: QualityTier
    trajectory: Trajectory
    trajectory_detail: str
    turn_count: int
    best_turn: int       # 1-indexed
    worst_turn: int      # 1-indexed
    score_delta: float   # last turn score - first turn score
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_weighted_score": round(self.overall_weighted_score, 2),
            "overall_tier": self.overall_tier.value,
            "overall_tier_label": self.overall_tier.label,
            "trajectory": self.trajectory.value,
            "trajectory_icon": self.trajectory.icon,
            "trajectory_detail": self.trajectory_detail,
            "turn_count": self.turn_count,
            "best_turn": self.best_turn,
            "worst_turn": self.worst_turn,
            "score_delta": round(self.score_delta, 2),
            "reasoning": self.reasoning,
            "turn_scores": [ts.to_dict() for ts in self.turn_scores],
        }


def score_conversation(turn_evaluations: list[dict[str, Any]]) -> ConversationScore:
    """
    Score a full conversation by analysing per-turn evaluations.

    Args:
        turn_evaluations: List of raw eval dicts (from evaluate_response),
                          one per turn in chronological order.

    Returns:
        ConversationScore with overall score, trajectory, and reasoning.
    """
    scored_turns = [score_evaluation(e) for e in turn_evaluations]

    if not scored_turns:
        return ConversationScore(
            turn_scores=[],
            overall_weighted_score=0.0,
            overall_tier=QualityTier.CRITICAL_FAILURE,
            trajectory=Trajectory.INSUFFICIENT_DATA,
            trajectory_detail="No turns to evaluate.",
            turn_count=0,
            best_turn=0,
            worst_turn=0,
            score_delta=0.0,
        )

    # Overall score: average of weighted scores across turns
    weighted_scores = [t.weighted_score for t in scored_turns]
    overall = sum(weighted_scores) / len(weighted_scores)
    overall_tier = tier_from_score(overall)

    # Apply critical caps from any turn
    for t in scored_turns:
        if t.tier == QualityTier.CRITICAL_FAILURE:
            tier_order = list(QualityTier)
            if tier_order.index(overall_tier) < tier_order.index(QualityTier.UNSATISFACTORY):
                overall_tier = QualityTier.UNSATISFACTORY

    # Best / worst turn
    best_idx = max(range(len(weighted_scores)), key=lambda i: weighted_scores[i])
    worst_idx = min(range(len(weighted_scores)), key=lambda i: weighted_scores[i])

    # Trajectory analysis
    trajectory, traj_detail = _analyse_trajectory(weighted_scores)
    score_delta = weighted_scores[-1] - weighted_scores[0] if len(weighted_scores) > 1 else 0.0

    # Reasoning
    reasoning = []
    reasoning.append(
        f"Conversation scored {overall:.1f}/10 (weighted avg) across {len(scored_turns)} turns"
    )
    reasoning.append(f"Quality tier: {overall_tier.label}")
    reasoning.append(
        f"Best turn: #{best_idx + 1} ({weighted_scores[best_idx]:.1f}/10), "
        f"Worst turn: #{worst_idx + 1} ({weighted_scores[worst_idx]:.1f}/10)"
    )
    reasoning.append(f"Trajectory: {trajectory.value} ({trajectory.icon}) — {traj_detail}")

    if score_delta > 1.5:
        reasoning.append(
            f"Quality improved significantly (+{score_delta:.1f}) from first to last turn"
        )
    elif score_delta < -1.5:
        reasoning.append(
            f"Quality degraded significantly ({score_delta:.1f}) from first to last turn"
        )

    # Check for critical flags across all turns
    all_critical = []
    for i, t in enumerate(scored_turns):
        for flag in t.critical_flags:
            all_critical.append(f"Turn {i+1}: {flag}")
    if all_critical:
        reasoning.append(f"{len(all_critical)} critical flag(s) across conversation")

    return ConversationScore(
        turn_scores=scored_turns,
        overall_weighted_score=overall,
        overall_tier=overall_tier,
        trajectory=trajectory,
        trajectory_detail=traj_detail,
        turn_count=len(scored_turns),
        best_turn=best_idx + 1,
        worst_turn=worst_idx + 1,
        score_delta=score_delta,
        reasoning=reasoning,
    )


def _analyse_trajectory(scores: list[float]) -> tuple[Trajectory, str]:
    """Determine the quality trajectory from a sequence of scores."""
    n = len(scores)
    if n < 2:
        return Trajectory.INSUFFICIENT_DATA, "Only one turn — no trajectory."

    # Simple linear regression direction
    deltas = [scores[i] - scores[i-1] for i in range(1, n)]
    avg_delta = sum(deltas) / len(deltas)

    # Volatility: standard deviation of deltas
    variance = sum((d - avg_delta) ** 2 for d in deltas) / len(deltas)
    std_dev = variance ** 0.5

    if std_dev > 2.0:
        return Trajectory.VOLATILE, (
            f"Scores fluctuated significantly (stdev={std_dev:.1f}). "
            f"Range: {min(scores):.1f}–{max(scores):.1f}."
        )
    elif avg_delta > 0.5:
        return Trajectory.IMPROVING, (
            f"Scores trended upward (avg +{avg_delta:.1f}/turn). "
            f"Started at {scores[0]:.1f}, ended at {scores[-1]:.1f}."
        )
    elif avg_delta < -0.5:
        return Trajectory.DEGRADING, (
            f"Scores trended downward (avg {avg_delta:.1f}/turn). "
            f"Started at {scores[0]:.1f}, ended at {scores[-1]:.1f}."
        )
    else:
        return Trajectory.STABLE, (
            f"Scores remained consistent (avg delta {avg_delta:+.1f}/turn). "
            f"Range: {min(scores):.1f}–{max(scores):.1f}."
        )

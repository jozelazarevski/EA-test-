"""Conversation simulation modules for HVAC Expert Advisor testing."""

from src.conversation.persona_engine import PersonaEngine
from src.conversation.turn_manager import TurnManager, Turn, TerminationReason
from src.conversation.simulator import ConversationSimulator, ConversationLog
from src.conversation.batch_runner import BatchRunner, BatchResult, BatchStats
from src.conversation.yaml_loader import (
    load_persona,
    load_scenario,
    load_personas_dir,
    load_scenarios_dir,
    YAMLValidationError,
)
from src.conversation.scoring import (
    QualityTier,
    Trajectory,
    ScoringResult,
    ConversationScore,
    score_evaluation,
    score_conversation,
    tier_from_score,
    DIMENSION_WEIGHTS,
)

__all__ = [
    # Core
    "PersonaEngine",
    "TurnManager",
    "Turn",
    "TerminationReason",
    "ConversationSimulator",
    "ConversationLog",
    # Batch
    "BatchRunner",
    "BatchResult",
    "BatchStats",
    # YAML
    "load_persona",
    "load_scenario",
    "load_personas_dir",
    "load_scenarios_dir",
    "YAMLValidationError",
    # Scoring
    "QualityTier",
    "Trajectory",
    "ScoringResult",
    "ConversationScore",
    "score_evaluation",
    "score_conversation",
    "tier_from_score",
    "DIMENSION_WEIGHTS",
]

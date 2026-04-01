"""
YAML Loader — Loads and validates persona and scenario YAML files.

Provides schema validation, safe YAML loading, and directory scanning
so callers can load individual files or entire directories of personas/scenarios.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema definitions (required keys + types)
# ---------------------------------------------------------------------------

_PERSONA_SCHEMA: dict[str, dict[str, Any]] = {
    "id":               {"type": str, "required": True},
    "name":             {"type": str, "required": True},
    "role":             {"type": str, "required": True},
    "experience_years": {"type": int, "required": True},
    "expertise_level":  {"type": str, "required": True,
                         "choices": ["none", "beginner", "intermediate", "advanced", "expert"]},
    "background":       {"type": str, "required": True},
    "communication_style": {"type": dict, "required": True, "keys": {
        "tone":             {"type": str, "required": True},
        "vocabulary":       {"type": str, "required": True},
        "typical_phrases":  {"type": list, "required": False},
    }},
    "question_domains":    {"type": list, "required": False},
    "follow_up_behavior":  {"type": str, "required": False},
    "evaluation_focus":    {"type": list, "required": False},
}

_SCENARIO_SCHEMA: dict[str, dict[str, Any]] = {
    "id":         {"type": str,  "required": True},
    "title":      {"type": str,  "required": True},
    "equipment":  {"type": str,  "required": True},
    "symptoms":   {"type": list, "required": True, "min_length": 1},
    "context":    {"type": str,  "required": False},
    "root_cause": {"type": str,  "required": False},
    "difficulty": {"type": str,  "required": False,
                   "choices": ["easy", "medium", "hard", "expert"]},
    "category":   {"type": str,  "required": False},
    "tags":       {"type": list, "required": False},
}


class YAMLValidationError(Exception):
    """Raised when a YAML file fails schema validation."""

    def __init__(self, path: str | Path, errors: list[str]) -> None:
        self.path = str(path)
        self.errors = errors
        super().__init__(f"Validation failed for {self.path}: {'; '.join(errors)}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_persona(path: str | Path) -> dict[str, Any]:
    """Load and validate a single persona YAML file."""
    data = _load_yaml(path)
    _validate(data, _PERSONA_SCHEMA, path)
    return data


def load_scenario(path: str | Path) -> dict[str, Any]:
    """Load and validate a single scenario YAML file."""
    data = _load_yaml(path)
    _validate(data, _SCENARIO_SCHEMA, path)
    return data


def load_personas_dir(directory: str | Path) -> list[dict[str, Any]]:
    """Load all persona YAML files from a directory (sorted by filename)."""
    return _load_dir(directory, load_persona)


def load_scenarios_dir(directory: str | Path) -> list[dict[str, Any]]:
    """Load all scenario YAML files from a directory (sorted by filename)."""
    return _load_dir(directory, load_scenario)


def load_persona_from_string(text: str, source: str = "<string>") -> dict[str, Any]:
    """Parse and validate persona YAML from a raw string."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise YAMLValidationError(source, ["Expected a YAML mapping, got " + type(data).__name__])
    _validate(data, _PERSONA_SCHEMA, source)
    return data


def load_scenario_from_string(text: str, source: str = "<string>") -> dict[str, Any]:
    """Parse and validate scenario YAML from a raw string."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise YAMLValidationError(source, ["Expected a YAML mapping, got " + type(data).__name__])
    _validate(data, _SCENARIO_SCHEMA, source)
    return data


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise YAMLValidationError(path, ["Expected a YAML mapping at top level"])
    return data


def _load_dir(directory: str | Path, loader) -> list:
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    results = []
    for p in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        try:
            results.append(loader(p))
        except (YAMLValidationError, yaml.YAMLError) as exc:
            logger.warning("Skipping %s: %s", p.name, exc)
    return results


def _validate(
    data: dict[str, Any],
    schema: dict[str, dict[str, Any]],
    source: str | Path,
) -> None:
    """Validate *data* against *schema*. Raises YAMLValidationError on failure."""
    errors: list[str] = []

    for key, rules in schema.items():
        value = data.get(key)

        # Required check
        if rules.get("required") and value is None:
            errors.append(f"Missing required field '{key}'")
            continue

        if value is None:
            continue

        # Type check
        expected_type = rules.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                f"Field '{key}' expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
            continue

        # Choices check
        if "choices" in rules and value not in rules["choices"]:
            errors.append(
                f"Field '{key}' must be one of {rules['choices']}, got '{value}'"
            )

        # Min length (for lists)
        if "min_length" in rules and isinstance(value, list) and len(value) < rules["min_length"]:
            errors.append(
                f"Field '{key}' requires at least {rules['min_length']} item(s), "
                f"got {len(value)}"
            )

        # Nested keys (for dicts like communication_style)
        if "keys" in rules and isinstance(value, dict):
            for sub_key, sub_rules in rules["keys"].items():
                sub_val = value.get(sub_key)
                if sub_rules.get("required") and sub_val is None:
                    errors.append(f"Missing required field '{key}.{sub_key}'")
                elif sub_val is not None:
                    sub_type = sub_rules.get("type")
                    if sub_type and not isinstance(sub_val, sub_type):
                        errors.append(
                            f"Field '{key}.{sub_key}' expected {sub_type.__name__}, "
                            f"got {type(sub_val).__name__}"
                        )

    if errors:
        raise YAMLValidationError(source, errors)

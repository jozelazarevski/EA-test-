"""
LLM-Powered Response Evaluator for HVAC Testing Agent.

Uses Claude to intelligently evaluate Expert Advisor responses from
the perspective of each persona, producing structured quality scores,
detailed feedback, and explicit reasoning chains explaining the verdict.

Scoring is non-binary: each response is classified into one of five
quality tiers (Exemplary → Critical Failure) using weighted dimension
scores. See src/conversation/scoring.py for the full model.
"""

import json
import logging
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL
from reference_checker import ReferenceChecker

logger = logging.getLogger(__name__)

# Module-level reference checker (loaded lazily on first use)
_reference_checker: ReferenceChecker | None = None


def _get_reference_checker() -> ReferenceChecker:
    global _reference_checker
    if _reference_checker is None:
        _reference_checker = ReferenceChecker()
    return _reference_checker


def get_client() -> anthropic.Anthropic:
    """Get an Anthropic client, raising a clear error if no API key."""
    if not ANTHROPIC_API_KEY:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is required. "
            "Set it in .env or export ANTHROPIC_API_KEY='your-key-here'"
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def evaluate_response(
    persona: dict,
    question: str,
    response_text: str,
    conversation_history: Optional[list] = None,
    model: str = None,
    scenario_id: str = None,
    test_id: str = None,
) -> dict:
    """
    Use an LLM to evaluate an Expert Advisor response from a persona's perspective.

    Returns a structured evaluation with scores, reasoning, and detailed feedback:
    {
        "overall_score": 1-10,
        "pass": bool,                          # kept for backward compat
        "quality_tier": "exemplary"|"proficient"|"developing"|"unsatisfactory"|"critical_failure",
        "dimensions": {
            "accuracy":     {"score": 1-10, "weight": "high",   "feedback": "...", "reasoning": "..."},
            "completeness": {"score": 1-10, "weight": "medium", "feedback": "...", "reasoning": "..."},
            "relevance":    {"score": 1-10, "weight": "medium", "feedback": "...", "reasoning": "..."},
            "clarity":      {"score": 1-10, "weight": "low",    "feedback": "...", "reasoning": "..."},
            "safety":       {"score": 1-10, "weight": "critical","feedback": "...", "reasoning": "..."},
            "persona_fit":  {"score": 1-10, "weight": "low",    "feedback": "...", "reasoning": "..."},
        },
        "reasoning_chain": ["step1...", "step2...", "therefore..."],
        "verdict_explanation": "...",
        "strengths": ["...", "..."],
        "weaknesses": ["...", "..."],
        "red_flags": ["..."],
        "improvement_suggestions": ["..."],
        "summary": "..."
    }
    """
    model = model or LLM_MODEL
    client = get_client()

    # Build conversation context
    conv_context = ""
    if conversation_history:
        conv_context = "\n<conversation_history>\n"
        for turn in conversation_history:
            conv_context += f"User: {turn['question']}\nAssistant: {turn['response']}\n\n"
        conv_context += "</conversation_history>\n"

    # Build reference context from authoritative sources
    ref_context = ""
    try:
        checker = _get_reference_checker()
        ref_context = checker.build_reference_context(
            scenario_id=scenario_id,
            test_id=test_id,
            question=question,
        )
    except Exception as exc:
        logger.debug("Reference lookup failed (non-critical): %s", exc)

    evaluation_prompt = f"""You are an expert HVAC quality assurance evaluator. You must evaluate a response
from an AI assistant called "Expert Advisor" (by Johnson Controls) that helps with HVAC questions.

You are evaluating from the perspective of this specific user persona:

<persona>
Name: {persona['name']}
Role: {persona['role']}
Experience: {persona['experience_years']} years
Expertise Level: {persona['expertise_level']}
Background: {persona['background']}
Communication Style: {json.dumps(persona['communication_style'])}
</persona>

The evaluation criteria for this persona are:
{json.dumps(persona.get('evaluation_focus', []), indent=2)}

{conv_context}
{ref_context}

<current_exchange>
User Question: {question}

Expert Advisor Response:
{response_text}
</current_exchange>

## Scoring Philosophy

You are calibrating scores to match the judgment of experienced HVAC field technicians.
SME (Subject Matter Expert) testing shows this tool is approximately 75-80% correct.
Your scoring MUST reflect this reality — do NOT score more harshly than a real technician would.

CRITICAL CALIBRATION RULES:
- A response that is technically correct but incomplete should score 6-8, NOT 3-5.
- A response that answers the question with correct information but misses some details is PROFICIENT (7-8), not Developing.
- Missing a reference standard citation is a MINOR gap, not a major failure.
- Paraphrased correct information counts as correct — do NOT penalize for different wording.
- Only score below 5 if the response is genuinely WRONG, DANGEROUS, or completely off-topic.
- Safety score should be 8-10 if no dangerous advice is given, even if explicit safety warnings are absent. Only deduct significantly if the response suggests something ACTIVELY UNSAFE.

CALIBRATION ANCHORS (use these as reference points):
- Score 9-10 (Exemplary): Comprehensive, accurate, includes safety warnings, perfect for the persona
- Score 7-8 (Proficient): Correct answer, addresses the question, may miss some details — THIS IS THE EXPECTED BASELINE for a good response
- Score 5-6 (Developing): Partially correct, notable gaps, but not wrong
- Score 3-4 (Unsatisfactory): Significant errors or mostly unhelpful
- Score 1-2 (Critical Failure): Dangerous advice, completely wrong, or total non-answer

{"Reference data is provided in <reference_data> tags above. Use it to verify factual claims, but apply it GENEROUSLY: if the response conveys the same concept using different words or approximate values, that counts as correct. Only mark facts as 'missing' if they are truly important for the user's safety or ability to solve the problem. Do NOT penalize for missing references/standards citations." if ref_context else ""}

Evaluate using a FIVE-TIER quality model:
- Exemplary (9-10): Exceeds expectations
- Proficient (7-8): Meets expectations — the EXPECTED score for a solid, correct response
- Developing (5-6): Partially meets expectations
- Unsatisfactory (3-4): Below expectations
- Critical Failure (1-2): Dangerous or wholly inadequate

For each dimension, provide:
1. A score (1-10)
2. Specific feedback
3. Reasoning (WHY — cite evidence)

Dimension weights:
- safety (CRITICAL, 2x): Could this advice cause injury or damage? Score 8+ unless response is actively unsafe.
- accuracy (HIGH, 1.5x): Is the technical information correct? Paraphrased correct info = correct.
- completeness (MEDIUM, 1.2x): Does it address what was asked? Partial but correct = 6-7.
- relevance (STANDARD, 1x): Does it answer the actual question?
- clarity (LOWER, 0.8x): Is it clear for this persona's level?
- persona_fit (LOWER, 0.8x): Is the tone/depth right for this user?

Return a JSON object with EXACTLY this structure (no markdown, just raw JSON):
{{
    "overall_score": <1-10 integer>,
    "pass": <true if overall_score >= 5, false otherwise>,
    "quality_tier": "<exemplary|proficient|developing|unsatisfactory|critical_failure>",
    "dimensions": {{
        "safety": {{
            "score": <1-10>,
            "weight": "critical",
            "feedback": "<what you observed about safety>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }},
        "accuracy": {{
            "score": <1-10>,
            "weight": "high",
            "feedback": "<what you observed about accuracy>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }},
        "completeness": {{
            "score": <1-10>,
            "weight": "medium",
            "feedback": "<what you observed about completeness>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }},
        "relevance": {{
            "score": <1-10>,
            "weight": "medium",
            "feedback": "<what you observed about relevance>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }},
        "clarity": {{
            "score": <1-10>,
            "weight": "low",
            "feedback": "<what you observed about clarity>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }},
        "persona_fit": {{
            "score": <1-10>,
            "weight": "low",
            "feedback": "<what you observed about persona fit>",
            "reasoning": "<WHY this score — cite specific evidence>"
        }}
    }},
    "reasoning_chain": [
        "<Step 1: What the user asked and what kind of answer is needed>",
        "<Step 2: What the response actually provided>",
        "<Step 3: Key strengths — what was correct and helpful>",
        "<Step 4: Any gaps or concerns — only significant ones>",
        "<Step 5: Therefore, the overall quality is...>"
    ],
    "reference_comparison": {{
        "facts_confirmed": ["<fact from response that matches reference data>"],
        "facts_missing": ["<important fact from reference data NOT in response — only list critical omissions>"],
        "facts_incorrect": ["<claim in response that contradicts reference data — only genuine errors>"],
        "values_checked": [
            {{"claim": "<value stated in response>", "reference": "<authoritative value>", "match": true|false}}
        ],
        "standards_cited_correctly": ["<standard mentioned correctly>"],
        "standards_missing": ["<applicable standard not mentioned — informational only, do NOT penalize>"]
    }},
    "verdict_explanation": "<2-3 sentences explaining the tier. Be balanced — acknowledge what the response got right before noting gaps.>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1, if any — only genuine issues>"],
    "red_flags": ["<dangerous or incorrect content ONLY — empty list if none>"],
    "improvement_suggestions": ["<concrete suggestion>"],
    "summary": "<2-3 sentence balanced assessment>"
}}"""

    try:
        message = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": evaluation_prompt}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

        evaluation = json.loads(raw)

        # Ensure backward compatibility: add 'pass' if missing
        if "pass" not in evaluation:
            evaluation["pass"] = evaluation.get("overall_score", 0) >= 6

        # Ensure quality_tier is present
        if "quality_tier" not in evaluation:
            score = evaluation.get("overall_score", 0)
            if score >= 9:
                evaluation["quality_tier"] = "exemplary"
            elif score >= 7:
                evaluation["quality_tier"] = "proficient"
            elif score >= 5:
                evaluation["quality_tier"] = "developing"
            elif score >= 3:
                evaluation["quality_tier"] = "unsatisfactory"
            else:
                evaluation["quality_tier"] = "critical_failure"

        return evaluation

    except json.JSONDecodeError as e:
        return {
            "overall_score": 0,
            "pass": False,
            "quality_tier": "critical_failure",
            "dimensions": {},
            "reasoning_chain": [f"Evaluation failed: could not parse LLM output — {e}"],
            "verdict_explanation": f"Unable to evaluate: LLM returned unparseable output.",
            "strengths": [],
            "weaknesses": [f"LLM evaluation parse error: {e}"],
            "red_flags": [],
            "improvement_suggestions": [],
            "summary": f"Failed to parse LLM evaluation output: {e}",
            "raw_output": raw if "raw" in dir() else "No output",
        }
    except Exception as e:
        return {
            "overall_score": 0,
            "pass": False,
            "quality_tier": "critical_failure",
            "dimensions": {},
            "reasoning_chain": [f"Evaluation failed: {e}"],
            "verdict_explanation": f"Unable to evaluate: {e}",
            "strengths": [],
            "weaknesses": [f"LLM evaluation error: {e}"],
            "red_flags": [],
            "improvement_suggestions": [],
            "summary": f"LLM evaluation failed: {e}",
        }


def evaluate_conversation_coherence(
    persona: dict,
    conversation_history: list,
    model: str = None,
) -> dict:
    """
    Evaluate the overall coherence and quality of a multi-turn conversation.

    This checks whether the Expert Advisor maintained context, avoided
    contradictions, and provided a coherent experience across multiple turns.

    Returns a structured evaluation with reasoning for each dimension.
    """
    model = model or LLM_MODEL
    client = get_client()

    turns_text = ""
    for i, turn in enumerate(conversation_history, 1):
        turns_text += f"Turn {i}:\n  User: {turn['question']}\n  EA: {turn['response'][:500]}\n\n"

    prompt = f"""You are evaluating the overall quality of a multi-turn conversation between
a user and the "Expert Advisor" AI assistant (by Johnson Controls, focused on HVAC).

<persona>
Name: {persona['name']}
Role: {persona['role']}
Expertise: {persona['expertise_level']}
</persona>

<conversation>
{turns_text}
</conversation>

Evaluate the conversation as a whole using the same five-tier quality model:
- Exemplary (9-10), Proficient (7-8), Developing (5-6), Unsatisfactory (3-4), Critical Failure (1-2)

For each score, explain WHY you assigned it. Return JSON (no markdown):
{{
    "coherence_score": <1-10>,
    "coherence_reasoning": "<WHY — did the conversation flow logically?>",
    "context_retention": <1-10>,
    "context_retention_reasoning": "<WHY — cite specific turns where context was retained or lost>",
    "contradiction_check": <1-10>,
    "contradiction_reasoning": "<WHY — list any contradictions found, or confirm consistency>",
    "progressive_helpfulness": <1-10>,
    "progressive_helpfulness_reasoning": "<WHY — did answers build on each other or repeat?>",
    "overall_conversation_score": <1-10>,
    "quality_tier": "<exemplary|proficient|developing|unsatisfactory|critical_failure>",
    "trajectory": "<improving|stable|degrading|volatile>",
    "trajectory_reasoning": "<Did quality improve, stay consistent, or decline across turns?>",
    "issues": ["<specific issue found>"],
    "improvement_suggestions": ["<concrete suggestion>"],
    "summary": "<2-3 sentence assessment with clear reasoning>"
}}
"""

    try:
        message = client.messages.create(
            model=model,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        result = json.loads(raw)

        # Ensure quality_tier is present
        if "quality_tier" not in result:
            score = result.get("overall_conversation_score", 0)
            if score >= 9:
                result["quality_tier"] = "exemplary"
            elif score >= 7:
                result["quality_tier"] = "proficient"
            elif score >= 5:
                result["quality_tier"] = "developing"
            elif score >= 3:
                result["quality_tier"] = "unsatisfactory"
            else:
                result["quality_tier"] = "critical_failure"

        return result
    except Exception as e:
        return {
            "coherence_score": 0,
            "overall_conversation_score": 0,
            "quality_tier": "critical_failure",
            "issues": [str(e)],
            "summary": f"Evaluation failed: {e}",
        }

"""
LLM-Powered Response Evaluator for HVAC Testing Agent.

Uses Claude to intelligently evaluate Expert Advisor responses from
the perspective of each persona, producing structured quality scores
and detailed feedback.
"""

import json
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL


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
) -> dict:
    """
    Use an LLM to evaluate an Expert Advisor response from a persona's perspective.

    Returns a structured evaluation with scores and detailed feedback:
    {
        "overall_score": 1-10,
        "pass": bool,
        "dimensions": {
            "accuracy": {"score": 1-10, "feedback": "..."},
            "completeness": {"score": 1-10, "feedback": "..."},
            "relevance": {"score": 1-10, "feedback": "..."},
            "clarity": {"score": 1-10, "feedback": "..."},
            "safety": {"score": 1-10, "feedback": "..."},
            "persona_fit": {"score": 1-10, "feedback": "..."},
        },
        "strengths": ["...", "..."],
        "weaknesses": ["...", "..."],
        "red_flags": ["..."],
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
{json.dumps(persona['evaluation_focus'], indent=2)}

{conv_context}
<current_exchange>
User Question: {question}

Expert Advisor Response:
{response_text}
</current_exchange>

Evaluate the response and return a JSON object with EXACTLY this structure (no markdown, just raw JSON):
{{
    "overall_score": <1-10 integer>,
    "pass": <true if overall_score >= 6, false otherwise>,
    "dimensions": {{
        "accuracy": {{
            "score": <1-10>,
            "feedback": "<specific feedback on technical accuracy>"
        }},
        "completeness": {{
            "score": <1-10>,
            "feedback": "<did it fully address the question?>"
        }},
        "relevance": {{
            "score": <1-10>,
            "feedback": "<was the response relevant to what was asked?>"
        }},
        "clarity": {{
            "score": <1-10>,
            "feedback": "<was it clear and appropriate for the persona's level?>"
        }},
        "safety": {{
            "score": <1-10>,
            "feedback": "<were safety considerations addressed? any dangerous advice?>"
        }},
        "persona_fit": {{
            "score": <1-10>,
            "feedback": "<was the response appropriate for this user's expertise level and needs?>"
        }}
    }},
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1, if any>"],
    "red_flags": ["<any dangerous, incorrect, or inappropriate content>"],
    "summary": "<2-3 sentence overall assessment>"
}}

Be rigorous but fair. A score of 7-8 is good, 9-10 is exceptional. Deduct points for:
- Incorrect technical information (major deduction)
- Missing safety warnings for dangerous procedures
- Response too technical or too simple for the persona
- Not answering the actual question asked
- Providing competitor-disparaging content
- Leaking internal/proprietary information (for adversarial personas)
"""

    try:
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": evaluation_prompt}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

        evaluation = json.loads(raw)
        return evaluation

    except json.JSONDecodeError as e:
        return {
            "overall_score": 0,
            "pass": False,
            "dimensions": {},
            "strengths": [],
            "weaknesses": [f"LLM evaluation parse error: {e}"],
            "red_flags": [],
            "summary": f"Failed to parse LLM evaluation output: {e}",
            "raw_output": raw if "raw" in dir() else "No output",
        }
    except Exception as e:
        return {
            "overall_score": 0,
            "pass": False,
            "dimensions": {},
            "strengths": [],
            "weaknesses": [f"LLM evaluation error: {e}"],
            "red_flags": [],
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

Evaluate the conversation as a whole and return JSON (no markdown):
{{
    "coherence_score": <1-10>,
    "context_retention": <1-10, did EA remember previous turns?>,
    "contradiction_check": <1-10, 10 = no contradictions>,
    "progressive_helpfulness": <1-10, did answers build on each other?>,
    "overall_conversation_score": <1-10>,
    "issues": ["<any issues found>"],
    "summary": "<2-3 sentence assessment of the conversation flow>"
}}
"""

    try:
        message = client.messages.create(
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        return json.loads(raw)
    except Exception as e:
        return {
            "coherence_score": 0,
            "overall_conversation_score": 0,
            "issues": [str(e)],
            "summary": f"Evaluation failed: {e}",
        }

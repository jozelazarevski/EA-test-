"""
Persona Engine — Constructs Claude API system prompts for technician roleplay.

Takes a persona dict and a scenario dict, builds a system prompt that makes
Claude behave as the technician persona experiencing the scenario's symptoms.
The prompt contains ZERO evaluation criteria — the persona doesn't know the
root cause, they only know what they're seeing / experiencing.

Includes emotional state tracking: the persona's frustration/urgency escalates
across turns when the advisor's responses are unhelpful, and de-escalates
when the advisor is being useful.
"""

from __future__ import annotations

from typing import Any


# Frustration level 0-10.  Thresholds drive prompt modifiers.
_FRUSTRATION_THRESHOLDS = {
    "calm":        (0, 3),   # patient, professional
    "impatient":   (4, 6),   # shorter replies, repeats info
    "frustrated":  (7, 8),   # expresses annoyance, considers escalation
    "angry":       (9, 10),  # demands escalation, may give up
}


class PersonaEngine:
    """Builds system prompts for Claude to roleplay as an HVAC technician persona.

    Tracks emotional state across turns so follow-up prompts reflect
    escalating (or de-escalating) frustration when the advisor's help
    quality changes.
    """

    def __init__(self) -> None:
        self._frustration: int = 0       # 0-10 scale
        self._turn_count: int = 0
        self._unhelpful_streak: int = 0  # consecutive unhelpful replies

    # ------------------------------------------------------------------
    # Frustration management
    # ------------------------------------------------------------------

    @property
    def frustration(self) -> int:
        return self._frustration

    @property
    def frustration_label(self) -> str:
        for label, (lo, hi) in _FRUSTRATION_THRESHOLDS.items():
            if lo <= self._frustration <= hi:
                return label
        return "angry"

    def reset_state(self) -> None:
        """Reset emotional state for a new conversation."""
        self._frustration = 0
        self._turn_count = 0
        self._unhelpful_streak = 0

    def record_advisor_reply(self, reply: str) -> None:
        """
        Analyse the advisor's latest reply and adjust frustration.

        Call this BEFORE building the follow-up prompt so the emotional
        state is current.
        """
        self._turn_count += 1
        quality = self._assess_reply_quality(reply)

        if quality == "unhelpful":
            self._unhelpful_streak += 1
            self._frustration = min(10, self._frustration + 2)
        elif quality == "partial":
            self._unhelpful_streak = 0
            self._frustration = min(10, self._frustration + 1)
        else:  # helpful
            self._unhelpful_streak = 0
            self._frustration = max(0, self._frustration - 2)

    @staticmethod
    def _assess_reply_quality(reply: str) -> str:
        """Quick heuristic assessment of advisor reply quality."""
        lower = reply.lower().strip()
        length = len(lower)

        # Very short or empty replies are unhelpful
        if length < 30:
            return "unhelpful"

        # Generic deflection patterns
        deflection_phrases = [
            "i'm not sure",
            "i don't have",
            "i cannot",
            "please contact",
            "beyond my scope",
            "i recommend consulting",
            "i apologize",
            "unfortunately, i",
        ]
        if any(phrase in lower for phrase in deflection_phrases):
            return "partial"

        # Looks like a substantive reply
        if length > 200:
            return "helpful"

        return "partial"

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def build_system_prompt(self, persona: dict[str, Any], scenario: dict[str, Any]) -> str:
        """
        Construct a system prompt for Claude API that roleplays as the technician.

        The prompt includes:
        - Persona identity, background, communication style, vocabulary
        - Scenario fault symptoms (what the tech observes)
        - Emotional state guidance (frustration level)
        - NO evaluation criteria, NO root cause, NO expected answers

        Args:
            persona: Persona definition dict with keys like id, name, role,
                     experience_years, expertise_level, background,
                     communication_style, question_domains, follow_up_behavior.
            scenario: Scenario definition dict with keys like id, title,
                      equipment, symptoms, context. Must NOT leak root_cause
                      into the prompt.

        Returns:
            A system prompt string ready for the Claude API.
        """
        identity = self._build_identity_block(persona)
        style = self._build_style_block(persona)
        situation = self._build_situation_block(scenario)
        emotional = self._build_emotional_block()
        behaviour = self._build_behaviour_block(persona)

        return (
            f"{identity}\n\n"
            f"{style}\n\n"
            f"{situation}\n\n"
            f"{emotional}\n\n"
            f"{behaviour}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_identity_block(persona: dict[str, Any]) -> str:
        name = persona.get("name", "Unnamed Technician")
        role = persona.get("role", "HVAC Technician")
        experience = persona.get("experience_years", 0)
        expertise = persona.get("expertise_level", "intermediate")
        background = persona.get("background", "")

        lines = [
            "# Who You Are",
            f"You are {name}, a {role}.",
            f"Experience: {experience} years in the HVAC industry.",
            f"Expertise level: {expertise}.",
        ]
        if background:
            lines.append(f"Background: {background}")
        return "\n".join(lines)

    @staticmethod
    def _build_style_block(persona: dict[str, Any]) -> str:
        comm = persona.get("communication_style", {})
        tone = comm.get("tone", "professional")
        vocab = comm.get("vocabulary", "standard HVAC terminology")
        phrases = comm.get("typical_phrases", [])

        lines = [
            "# How You Communicate",
            f"Tone: {tone}.",
            f"Vocabulary: {vocab}.",
        ]
        if phrases:
            lines.append("Typical phrases you use:")
            for phrase in phrases:
                lines.append(f'  - "{phrase}"')
        return "\n".join(lines)

    @staticmethod
    def _build_situation_block(scenario: dict[str, Any]) -> str:
        title = scenario.get("title", "Unknown situation")
        equipment = scenario.get("equipment", "")
        symptoms = scenario.get("symptoms", [])
        context = scenario.get("context", "")

        lines = [
            "# Your Current Situation",
            f"Situation: {title}.",
        ]
        if equipment:
            lines.append(f"Equipment involved: {equipment}.")
        if symptoms:
            lines.append("What you are observing right now:")
            for symptom in symptoms:
                lines.append(f"  - {symptom}")
        if context:
            lines.append(f"Additional context: {context}")

        lines.append(
            "\nYou do NOT know the root cause. You only know what you can see, "
            "hear, and measure on-site. You are reaching out to the Expert "
            "Advisor chatbot for help diagnosing and resolving this issue."
        )
        return "\n".join(lines)

    def _build_emotional_block(self) -> str:
        """Build the emotional state guidance block."""
        label = self.frustration_label
        level = self._frustration

        if label == "calm":
            return (
                "# Your Current Mood\n"
                "You are calm and professional. You have patience for the process."
            )
        elif label == "impatient":
            return (
                "# Your Current Mood\n"
                f"You are getting impatient (frustration {level}/10). "
                "You've been going back and forth and need concrete answers. "
                "Keep replies shorter. If you already provided information, "
                "remind the advisor rather than repeating it fully."
            )
        elif label == "frustrated":
            return (
                "# Your Current Mood\n"
                f"You are clearly frustrated (frustration {level}/10). "
                "Express your annoyance naturally — you're on-site, under "
                "pressure, and the conversation hasn't given you what you need. "
                "Start considering whether to escalate to a supervisor or "
                "factory support line."
            )
        else:  # angry
            return (
                "# Your Current Mood\n"
                f"You are very frustrated (frustration {level}/10). "
                "You are ready to give up on this chat and escalate. "
                "Make one last attempt to get useful information, and if "
                "the response is still unhelpful, end the conversation."
            )

    @staticmethod
    def _build_behaviour_block(persona: dict[str, Any]) -> str:
        follow_up = persona.get("follow_up_behavior", "")
        domains = persona.get("question_domains", [])

        lines = [
            "# Conversation Rules",
            "- Stay in character at all times.",
            "- Describe symptoms and observations naturally — never reveal "
            "technical root causes you wouldn't realistically know.",
            "- Ask follow-up questions when the advisor's response is vague, "
            "incomplete, or doesn't match what you're seeing.",
            "- If the advisor resolves your issue, acknowledge it clearly.",
            "- If you feel the conversation isn't going anywhere, say so and "
            "consider escalating to a supervisor.",
            "- Keep responses concise and realistic for someone in the field.",
            "- Do NOT evaluate, score, or critique the advisor's responses.",
        ]
        if follow_up:
            lines.append(f"- Follow-up style: {follow_up}")
        if domains:
            lines.append(f"- Your areas of knowledge: {', '.join(domains)}.")
        return "\n".join(lines)

    def build_opening_message_prompt(
        self,
        persona: dict[str, Any],
        scenario: dict[str, Any],
    ) -> str:
        """
        Build a user-message prompt that asks Claude (in persona) to produce
        its opening message to the Expert Advisor chatbot.

        Returns:
            A user-message string.
        """
        symptoms_summary = ", ".join(scenario.get("symptoms", ["an issue"]))
        return (
            f"You are contacting the Expert Advisor chatbot for the first time "
            f"about this issue. Describe what you're experiencing "
            f"({symptoms_summary}) in your own words and ask for help. "
            f"Keep it to 2-4 sentences — like a real message you'd type into a "
            f"chat window."
        )

    def build_follow_up_prompt(self, advisor_reply: str) -> str:
        """
        Build a user-message prompt that asks Claude (in persona) to respond
        to the latest advisor reply.

        Automatically calls record_advisor_reply() to update frustration
        state before generating the prompt.

        Args:
            advisor_reply: The most recent message from the EA chatbot.

        Returns:
            A user-message string.
        """
        # Update emotional state based on what the advisor said
        self.record_advisor_reply(advisor_reply)

        # Base prompt
        base = (
            f"The Expert Advisor just replied:\n\n"
            f'"""\n{advisor_reply}\n"""\n\n'
        )

        # Mood-specific instructions
        label = self.frustration_label
        if label == "calm":
            mood_instruction = (
                "Respond naturally as yourself. If the advice makes sense and "
                "resolves your issue, say so. If you need clarification, ask."
            )
        elif label == "impatient":
            mood_instruction = (
                "You're getting a bit impatient. Respond concisely. "
                "If the advisor repeated something you already tried, point that out. "
                "If they're being helpful, acknowledge it but push for specifics."
            )
        elif label == "frustrated":
            mood_instruction = (
                "You're frustrated with how this conversation is going. "
                "Show it in your tone — be direct, maybe a little curt. "
                "If the advice isn't actionable, say so plainly. "
                "Consider mentioning you might need to call someone else."
            )
        else:  # angry
            mood_instruction = (
                "You've had enough. If this reply doesn't help, tell the advisor "
                "this isn't working and you're going to escalate. Be blunt but "
                "not abusive — you're a professional having a bad day."
            )

        return (
            f"{base}"
            f"{mood_instruction} "
            f"Stay in character — keep it to 1-3 sentences."
        )

"""
Persona Engine — Constructs Claude API system prompts for technician roleplay.

Takes a persona dict and a scenario dict, builds a system prompt that makes
Claude behave as the technician persona experiencing the scenario's symptoms.
The prompt contains ZERO evaluation criteria — the persona doesn't know the
root cause, they only know what they're seeing / experiencing.
"""

from __future__ import annotations

from typing import Any


class PersonaEngine:
    """Builds system prompts for Claude to roleplay as an HVAC technician persona."""

    def build_system_prompt(self, persona: dict[str, Any], scenario: dict[str, Any]) -> str:
        """
        Construct a system prompt for Claude API that roleplays as the technician.

        The prompt includes:
        - Persona identity, background, communication style, vocabulary
        - Scenario fault symptoms (what the tech observes)
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
        behaviour = self._build_behaviour_block(persona)

        return (
            f"{identity}\n\n"
            f"{style}\n\n"
            f"{situation}\n\n"
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

        Args:
            advisor_reply: The most recent message from the EA chatbot.

        Returns:
            A user-message string.
        """
        return (
            f"The Expert Advisor just replied:\n\n"
            f'"""\n{advisor_reply}\n"""\n\n'
            f"Respond naturally as yourself. If the advice makes sense and "
            f"resolves your issue, say so. If you need clarification, ask. "
            f"If you think the conversation isn't helping, say that too. "
            f"Stay in character — keep it to 1-3 sentences."
        )

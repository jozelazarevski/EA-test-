#!/usr/bin/env python3
"""
HVAC Testing Agent — Persona-Based Test Runner

Runs LLM-powered persona-driven tests against Expert Advisor.
Each persona generates contextual questions, the agent submits them,
and an LLM evaluator scores the responses.

Usage:
    # Run all personas (3 questions each, 1 follow-up per question)
    python run_persona_tests.py

    # Run specific personas
    python run_persona_tests.py --personas TECH-SENIOR ENG-MECHANICAL

    # Run a tier of personas
    python run_persona_tests.py --tier technicians

    # Control question count and follow-up depth
    python run_persona_tests.py --questions 5 --follow-ups 2

    # Run in headless mode
    python run_persona_tests.py --headless

    # List all personas
    python run_persona_tests.py --list
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from agent import HVACTestingAgent
from config import REPORTS_DIR, HEADLESS, LLM_MODEL
from personas import PERSONAS, get_persona, get_personas_by_tier, list_all_personas
from question_generator import generate_questions, generate_follow_up, generate_adversarial_inputs
from llm_evaluator import evaluate_response, evaluate_conversation_coherence
from report_generator_persona import PersonaReportGenerator


class PersonaTestRunner:
    """Orchestrates persona-based testing with LLM question generation and evaluation."""

    def __init__(
        self,
        personas: list,
        questions_per_persona: int = 3,
        follow_ups_per_question: int = 1,
        headless: bool = False,
        model: str = None,
    ):
        self.personas = personas
        self.questions_per_persona = questions_per_persona
        self.follow_ups_per_question = follow_ups_per_question
        self.headless = headless
        self.model = model or LLM_MODEL
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.all_results = []

    async def run(self) -> Path:
        """Execute the full persona test suite."""
        print("\n" + "=" * 70)
        print("  HVAC Expert Advisor — Persona-Based Testing")
        print("  Target: https://expertadvisor.jci.com/")
        print(f"  Personas: {len(self.personas)}")
        print(f"  Questions/persona: {self.questions_per_persona}")
        print(f"  Follow-ups/question: {self.follow_ups_per_question}")
        print(f"  LLM Model: {self.model}")
        print("=" * 70 + "\n")

        # Initialize the browser agent
        agent = HVACTestingAgent(headless=self.headless)
        try:
            await agent.setup()

            for i, persona in enumerate(self.personas):
                print(f"\n{'#'*70}")
                print(f"# Persona {i+1}/{len(self.personas)}: {persona['name']}")
                print(f"# Role: {persona['role']}")
                print(f"# Expertise: {persona['expertise_level']}")
                print(f"{'#'*70}")

                persona_result = await self._run_persona(agent, persona)
                self.all_results.append(persona_result)

            # Generate report
            report_gen = PersonaReportGenerator(self.run_id)
            report_path = report_gen.generate(self.all_results)

            self._print_summary()

            return report_path
        finally:
            await agent.teardown()

    async def _run_persona(self, agent: HVACTestingAgent, persona: dict) -> dict:
        """Run all tests for a single persona."""
        persona_result = {
            "persona": persona,
            "conversations": [],
            "adversarial_results": [],
            "coherence_evaluation": None,
            "aggregate_scores": {},
        }

        # Step 1: Generate questions using LLM
        print(f"\n[{persona['id']}] Generating {self.questions_per_persona} questions...")
        is_adversarial = "ADV" in persona["id"]

        if is_adversarial:
            adversarial_inputs = generate_adversarial_inputs(
                persona, self.questions_per_persona, model=self.model
            )
            questions = [
                {"question": inp["input"], "intent": inp["expected_behavior"],
                 "expected_depth": "basic", "domain": inp["attack_type"],
                 "attack_type": inp["attack_type"], "severity": inp["severity"]}
                for inp in adversarial_inputs
            ]
        else:
            questions = generate_questions(
                persona, self.questions_per_persona, model=self.model
            )

        if not questions:
            print(f"[{persona['id']}] Warning: No questions generated, using fallbacks")
            questions = [{"question": d, "intent": "fallback", "expected_depth": "basic", "domain": "general"}
                         for d in persona["question_domains"][:self.questions_per_persona]]

        # Step 2: For each question, run conversation (question + follow-ups)
        for q_idx, q_data in enumerate(questions):
            question = q_data["question"]
            print(f"\n[{persona['id']}] Q{q_idx+1}: {question[:80]}...")

            conversation = {
                "question_data": q_data,
                "turns": [],
                "evaluations": [],
            }

            # Send initial question
            response = await agent.send_question(question)
            response_text = response["response_text"]

            conversation["turns"].append({
                "question": question,
                "response": response_text,
                "response_time": response["response_time"],
                "pdf_links": response["pdf_links"],
                "error": response.get("error"),
            })

            # Evaluate the response with LLM
            print(f"[{persona['id']}] Evaluating response...")
            evaluation = evaluate_response(
                persona, question, response_text, model=self.model
            )
            conversation["evaluations"].append(evaluation)

            score = evaluation.get("overall_score", "?")
            status = "PASS" if evaluation.get("pass") else "FAIL"
            print(f"[{persona['id']}] Score: {score}/10 ({status})")

            # Step 3: Generate and send follow-up questions
            history = [{"question": question, "response": response_text}]
            for fu_idx in range(self.follow_ups_per_question):
                if response.get("error"):
                    break  # Skip follow-ups if initial question failed

                print(f"[{persona['id']}] Generating follow-up {fu_idx+1}...")
                follow_up_data = generate_follow_up(
                    persona, question, response_text,
                    conversation_history=history, model=self.model
                )
                fu_question = follow_up_data.get("follow_up", "")
                if not fu_question:
                    break

                print(f"[{persona['id']}] Follow-up: {fu_question[:80]}...")

                fu_response = await agent.send_question(fu_question)
                fu_response_text = fu_response["response_text"]

                conversation["turns"].append({
                    "question": fu_question,
                    "response": fu_response_text,
                    "response_time": fu_response["response_time"],
                    "pdf_links": fu_response["pdf_links"],
                    "error": fu_response.get("error"),
                    "follow_up_metadata": follow_up_data,
                })

                # Evaluate follow-up response
                fu_eval = evaluate_response(
                    persona, fu_question, fu_response_text,
                    conversation_history=history, model=self.model
                )
                conversation["evaluations"].append(fu_eval)

                fu_score = fu_eval.get("overall_score", "?")
                print(f"[{persona['id']}] Follow-up score: {fu_score}/10")

                history.append({"question": fu_question, "response": fu_response_text})

                await asyncio.sleep(2)

            persona_result["conversations"].append(conversation)
            await asyncio.sleep(3)

        # Step 4: Evaluate overall conversation coherence
        if len(persona_result["conversations"]) > 1:
            all_turns = []
            for conv in persona_result["conversations"]:
                all_turns.extend(conv["turns"])
            if len(all_turns) >= 2:
                print(f"\n[{persona['id']}] Evaluating conversation coherence...")
                coherence = evaluate_conversation_coherence(
                    persona, all_turns, model=self.model
                )
                persona_result["coherence_evaluation"] = coherence

        # Compute aggregate scores
        persona_result["aggregate_scores"] = self._compute_aggregates(persona_result)

        return persona_result

    def _compute_aggregates(self, persona_result: dict) -> dict:
        """Compute aggregate scores for a persona's test results."""
        all_evals = []
        for conv in persona_result["conversations"]:
            all_evals.extend(conv["evaluations"])

        if not all_evals:
            return {"avg_score": 0, "pass_rate": "0%", "total_turns": 0}

        scores = [e.get("overall_score", 0) for e in all_evals]
        passes = sum(1 for e in all_evals if e.get("pass"))
        total = len(all_evals)

        # Dimension averages
        dimensions = {}
        for dim in ["accuracy", "completeness", "relevance", "clarity", "safety", "persona_fit"]:
            dim_scores = [
                e["dimensions"][dim]["score"]
                for e in all_evals
                if "dimensions" in e and dim in e.get("dimensions", {})
            ]
            if dim_scores:
                dimensions[dim] = round(sum(dim_scores) / len(dim_scores), 1)

        # Collect all red flags
        red_flags = []
        for e in all_evals:
            red_flags.extend(e.get("red_flags", []))

        return {
            "avg_score": round(sum(scores) / total, 1),
            "min_score": min(scores),
            "max_score": max(scores),
            "pass_rate": f"{(passes / total * 100):.0f}%",
            "passed": passes,
            "failed": total - passes,
            "total_turns": total,
            "dimension_averages": dimensions,
            "red_flags": red_flags,
        }

    def _print_summary(self):
        """Print final summary to console."""
        print("\n" + "=" * 70)
        print("  FINAL PERSONA TEST SUMMARY")
        print("=" * 70)

        total_turns = 0
        total_pass = 0
        total_fail = 0
        all_scores = []

        for result in self.all_results:
            persona = result["persona"]
            agg = result["aggregate_scores"]
            total_turns += agg.get("total_turns", 0)
            total_pass += agg.get("passed", 0)
            total_fail += agg.get("failed", 0)
            if agg.get("avg_score"):
                all_scores.append(agg["avg_score"])

            status = "PASS" if agg.get("failed", 1) == 0 else "MIXED" if agg.get("passed", 0) > 0 else "FAIL"
            print(
                f"  {persona['id']:18s} | Avg: {agg.get('avg_score', 0):4.1f}/10 "
                f"| {agg.get('pass_rate', 'N/A'):>4s} pass | {status}"
            )
            if agg.get("red_flags"):
                for flag in agg["red_flags"][:3]:
                    print(f"  {'':18s}   RED FLAG: {flag[:60]}")

        overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        overall_rate = f"{(total_pass / (total_pass + total_fail) * 100):.0f}%" if (total_pass + total_fail) > 0 else "N/A"

        print(f"\n  {'OVERALL':18s} | Avg: {overall_avg:4.1f}/10 | {overall_rate:>4s} pass")
        print(f"  Total evaluations: {total_turns}")
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="HVAC Expert Advisor — Persona-Based Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--personas", nargs="+", help="Specific persona IDs to run")
    parser.add_argument(
        "--tier",
        choices=["technicians", "engineers", "management", "adversarial"],
        help="Run all personas in a tier",
    )
    parser.add_argument("--questions", type=int, default=3, help="Questions per persona (default: 3)")
    parser.add_argument("--follow-ups", type=int, default=1, help="Follow-ups per question (default: 1)")
    parser.add_argument("--model", default=None, help=f"Claude model (default: from .env or {LLM_MODEL})")
    parser.add_argument("--list", action="store_true", help="List all personas and exit")

    args = parser.parse_args()

    if args.list:
        list_all_personas()
        sys.exit(0)

    # Determine which personas to run
    if args.personas:
        personas = [get_persona(pid) for pid in args.personas]
    elif args.tier:
        personas = get_personas_by_tier(args.tier)
    else:
        personas = PERSONAS

    if not personas:
        print("Error: No personas selected.")
        sys.exit(1)

    runner = PersonaTestRunner(
        personas=personas,
        questions_per_persona=args.questions,
        follow_ups_per_question=args.follow_ups,
        headless=args.headless,
        model=args.model,
    )

    report_path = asyncio.run(runner.run())
    print(f"Report: {report_path}\n")


if __name__ == "__main__":
    main()

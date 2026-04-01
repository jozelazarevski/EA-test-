#!/usr/bin/env python3
"""
HVAC Testing Agent - Main Entry Point

All tests are evaluated using LLM-powered quality assessment (requires
ANTHROPIC_API_KEY).

Usage:
    # Run all tests (browser visible)
    python run_agent.py

    # Run in headless mode
    python run_agent.py --headless

    # Run specific test cases
    python run_agent.py --tests CHILLER-001 AHU-001 CTRL-001

    # Run a single category
    python run_agent.py --category "Chiller Systems"

    # Use a specific model
    python run_agent.py --model claude-sonnet-4-6

    # List all available test cases
    python run_agent.py --list
"""

import argparse
import asyncio
import sys

from agent import HVACTestingAgent
from hvac_test_cases import TEST_CASES


def list_test_cases():
    """Print all available test cases."""
    print("\nAvailable HVAC Test Cases:")
    print(f"{'='*80}")

    current_category = None
    for tc in TEST_CASES:
        if tc["category"] != current_category:
            current_category = tc["category"]
            print(f"\n  [{current_category}]")
        question_preview = tc["question"][:60]
        if len(tc["question"]) > 60:
            question_preview += "..."
        pdf_marker = " [PDF]" if tc.get("expect_pdf") else ""
        print(f"    {tc['id']:15s} {question_preview}{pdf_marker}")

    print(f"\n{'='*80}")
    print(f"Total: {len(TEST_CASES)} test cases\n")


def main():
    parser = argparse.ArgumentParser(
        description="HVAC Expert Advisor Testing Agent (LLM-evaluated)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py                              # Run all tests
  python run_agent.py --headless                   # Headless mode
  python run_agent.py --tests CHILLER-001 AHU-001  # Specific tests
  python run_agent.py --category "Chiller Systems" # One category
  python run_agent.py --model claude-sonnet-4-6    # Custom model
  python run_agent.py --list                       # List all tests
        """,
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        help="Run specific test case IDs (e.g., CHILLER-001 AHU-001)",
    )
    parser.add_argument(
        "--category",
        type=str,
        help='Run all tests in a category (e.g., "Chiller Systems")',
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the Claude model used for evaluation",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available test cases and exit",
    )
    parser.add_argument(
        "--no-session",
        action="store_true",
        help="Disable session persistence (always re-login)",
    )
    parser.add_argument(
        "--clear-session",
        action="store_true",
        help="Clear saved session and re-login",
    )

    args = parser.parse_args()

    if args.list:
        list_test_cases()
        sys.exit(0)

    # Require API key
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY is required for LLM evaluation.")
        print("Set it in .env or: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    if args.clear_session:
        from session_manager import SessionManager
        SessionManager().clear()
        print("Saved session cleared.")

    # Determine which tests to run
    test_ids = None
    if args.tests:
        test_ids = args.tests
        # Validate test IDs
        valid_ids = {tc["id"] for tc in TEST_CASES}
        invalid = set(test_ids) - valid_ids
        if invalid:
            print(f"Error: Unknown test IDs: {', '.join(invalid)}")
            print("Use --list to see available test cases.")
            sys.exit(1)
    elif args.category:
        test_ids = [
            tc["id"] for tc in TEST_CASES if tc["category"] == args.category
        ]
        if not test_ids:
            categories = sorted(set(tc["category"] for tc in TEST_CASES))
            print(f"Error: Unknown category '{args.category}'")
            print(f"Available categories: {', '.join(categories)}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("  HVAC Expert Advisor Testing Agent")
    print("  Target: https://expertadvisor.jci.com/")
    print("  Evaluation: LLM-powered (6-dimension scoring)")
    print("=" * 60)

    if test_ids:
        print(f"  Tests to run: {len(test_ids)}")
    else:
        print(f"  Tests to run: {len(TEST_CASES)} (all)")
    print(f"  Mode: {'headless' if args.headless else 'visible browser'}")
    if args.model:
        print(f"  Model: {args.model}")
    print("=" * 60 + "\n")

    persist = not args.no_session
    agent = HVACTestingAgent(
        headless=args.headless,
        test_ids=test_ids,
        persist_session=persist,
        model=args.model,
    )

    report_path = asyncio.run(agent.run())

    # Print final summary
    total = len(agent.results)
    scores = [r["evaluation"].get("overall_score", 0) for r in agent.results]
    avg_score = sum(scores) / len(scores) if scores else 0
    passed = sum(1 for s in scores if s >= 6)
    failed = total - passed

    # Tier distribution
    tiers = {}
    for r in agent.results:
        tier = r["evaluation"].get("quality_tier", "unknown")
        tiers[tier] = tiers.get(tier, 0) + 1

    tier_icons = {
        "exemplary": "★★", "proficient": "★", "developing": "◐",
        "unsatisfactory": "▽", "critical_failure": "✖",
    }

    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    print(f"  Total:      {total}")
    print(f"  Avg Score:  {avg_score:.1f}/10")
    print(f"  Passed:     {passed} (score >= 6)")
    print(f"  Failed:     {failed} (score < 6)")
    print(f"  Pass Rate:  {(passed/total*100):.1f}%" if total > 0 else "  Pass Rate:  N/A")
    print()
    print("  Tier Distribution:")
    for tier_name in ["exemplary", "proficient", "developing", "unsatisfactory", "critical_failure"]:
        count = tiers.get(tier_name, 0)
        if count > 0:
            icon = tier_icons.get(tier_name, "")
            print(f"    {icon} {tier_name.replace('_', ' ').title():20s} {count}")
    print(f"\n  Report: {report_path}")
    print("=" * 60 + "\n")

    # Exit with non-zero if average score is below threshold
    sys.exit(0 if avg_score >= 6.0 else 1)


if __name__ == "__main__":
    main()

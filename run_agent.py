#!/usr/bin/env python3
"""
HVAC Testing Agent - Main Entry Point

Usage:
    # Run all tests (browser visible)
    python run_agent.py

    # Run in headless mode
    python run_agent.py --headless

    # Run specific test cases
    python run_agent.py --tests CHILLER-001 AHU-001 CTRL-001

    # Run a single category
    python run_agent.py --category "Chiller Systems"

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
        pdf_marker = " [PDF]" if tc["validation"].get("expect_pdf") else ""
        print(f"    {tc['id']:15s} {question_preview}{pdf_marker}")

    print(f"\n{'='*80}")
    print(f"Total: {len(TEST_CASES)} test cases\n")


def main():
    parser = argparse.ArgumentParser(
        description="HVAC Expert Advisor Testing Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py                              # Run all tests
  python run_agent.py --headless                   # Headless mode
  python run_agent.py --tests CHILLER-001 AHU-001  # Specific tests
  python run_agent.py --category "Chiller Systems" # One category
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
    print("=" * 60)

    if test_ids:
        print(f"  Tests to run: {len(test_ids)}")
    else:
        print(f"  Tests to run: {len(TEST_CASES)} (all)")
    print(f"  Mode: {'headless' if args.headless else 'visible browser'}")
    print("=" * 60 + "\n")

    persist = not args.no_session
    agent = HVACTestingAgent(headless=args.headless, test_ids=test_ids, persist_session=persist)

    report_path = asyncio.run(agent.run())

    # Print final summary
    total = len(agent.results)
    passed = sum(
        1 for r in agent.results if r["validation_results"]["overall_pass"]
    )
    failed = total - passed

    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    print(f"  Total:  {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Rate:   {(passed/total*100):.1f}%" if total > 0 else "  Rate:   N/A")
    print(f"\n  Report: {report_path}")
    print("=" * 60 + "\n")

    # Exit with non-zero if any tests failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
XMUOJ Auto Answer - Main Runner
Usage:
    python run.py                          # Run with env var config
    python run.py --contest 362 --limit 2   # Contest 362, first 2 problems
    python run.py --contest 361 --range 12-30        # Contest 361, problems 12-30
    python run.py --contest 361 --problems JD027,JD029,7318  # Specific problems
    python run.py --dry-run                # Test connections only (no submit)
"""
import argparse
import asyncio
import os
import sys

from config import config
from orchestrator import Orchestrator


async def dry_run():
    """Test connections without AI solving."""
    print("=" * 60)
    print("  DRY RUN - Testing connections only")
    print("=" * 60)

    from auth import XMUOJAuth
    from fetcher import ProblemFetcher

    async with XMUOJAuth() as auth:
        if not await auth.login():
            print("FAIL: Login failed!")
            return False

        print("OK: Login successful")

        if not await auth.access_contest(config.contest_id):
            print("FAIL: Could not access contest!")
            return False

        print("OK: Contest access successful")

        fetcher = ProblemFetcher(auth.page)
        problems = await fetcher.get_contest_problems(config.contest_id)
        print(f"OK: Found {len(problems)} problems:")
        for p in problems:
            print(f"    #{p.problem_id}: {p.title}")

        # Try fetching details for first problem
        if problems:
            detail = await fetcher.get_problem_detail(problems[0].problem_id)
            print(f"OK: Fetched detail for problem #{detail.problem_id}")
            print(f"    Description length: {len(detail.description)} chars")
            print(f"    Sample input: {detail.sample_input[:100]}")

        print("\n✓ All checks passed! Ready for full run.")
        return True


async def solve_single(problem_id: str):
    """Solve a single problem."""
    from auth import XMUOJAuth
    from fetcher import ProblemFetcher
    from orchestrator import Orchestrator

    async with XMUOJAuth() as auth:
        if not await auth.login():
            print("FATAL: Login failed!")
            return

        if not await auth.access_contest(config.contest_id):
            print("FATAL: Could not access contest!")
            return

        fetcher = ProblemFetcher(auth.page)
        problem = await fetcher.get_problem_detail(problem_id)

        orch = Orchestrator()
        orch.auth = auth
        orch.fetcher = fetcher
        orch.submitter = __import__('submit_engine', fromlist=['SubmitEngine']).SubmitEngine(auth.page)
        orch.monitor = __import__('submit_engine', fromlist=['ResultMonitor']).ResultMonitor(auth.page)

        result = await orch._solve_problem(problem)
        print(f"\nResult: {'✓ SOLVED' if result.solved else '✗ FAILED'}")
        print(f"Score: {result.final_score}")
        print(f"Attempts: {len(result.attempts)}")


def main():
    parser = argparse.ArgumentParser(
        description='XMUOJ Auto Answer - Automated problem solving bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                           # Run full automation
  python run.py --dry-run                 # Test connections only
  python run.py --single 123              # Solve only problem #123
  python run.py --contest 362             # Specify contest
  python run.py --max-retries 3           # Max 3 retries per problem
  python run.py --headless                # Run browser headless (default)
  python run.py --no-headless             # Show browser window
  python run.py --limit 2                 # Test: only first 2 problems

Configuration:
  Set credentials via environment variables:
    $env:XMUOJ_USERNAME = "your_username"
    $env:XMUOJ_PASSWORD = "your_password"
    $env:XMUOJ_CONTEST_PASSWORD = "contest_password"

  Or edit config.py directly.
        """
    )
    parser.add_argument('--contest', type=int, default=362,
                        help='Contest ID (default: 362)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test connections without AI solving')
    parser.add_argument('--single', type=str, metavar='PROBLEM_ID',
                        help='Solve a single problem only')
    parser.add_argument('--max-retries', type=int, default=None,
                        help='Max AI retries per problem')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')
    parser.add_argument('--no-headless', action='store_true',
                        help='Show browser window')
    parser.add_argument('--model', type=str, default=None,
                        help='AI model to use')
    parser.add_argument('-l', '--language', type=str, default=None,
                        choices=['cpp', 'c', 'python', 'java'],
                        help='Output language: cpp, c, python, java (default: cpp)')
    parser.add_argument('-d', '--delay', type=float, default=None,
                        help='Base delay in seconds (default: 3, higher = safer)')
    parser.add_argument('--fast', action='store_true',
                        help='Minimal delay mode (risk of rate limit)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit to first N problems (for testing)')
    parser.add_argument('--range', type=str, default=None,
                        help='Solve problems in range, e.g. "12-30" (1-indexed)')
    parser.add_argument('--problems', type=str, default=None,
                        help='Solve specific problems by display_id or numeric id, e.g. "JD027,JD029,7318"')

    args = parser.parse_args()

    # Apply config overrides
    config.contest_id = args.contest
    if args.max_retries is not None:
        config.max_retry_per_problem = args.max_retries
    if args.no_headless:
        config.headless = False
    if args.model:
        config.ai_model = args.model
    if args.language:
        config.language = args.language
    if args.fast:
        config.delay_seconds = 0.5
        config.poll_interval = 1.0
    if args.delay is not None:
        config.delay_seconds = args.delay

    # Parse range / problems filter
    problem_range = None
    problem_ids = None
    if args.range:
        parts = args.range.split('-')
        if len(parts) == 2:
            problem_range = (int(parts[0]), int(parts[1]))
    if args.problems:
        problem_ids = [p.strip() for p in args.problems.split(',') if p.strip()]

    # Validate config (except for dry run which tests auth differently)
    if not args.dry_run:
        try:
            config.validate()
        except ValueError as e:
            print(f"Configuration error: {e}")
            print("\nPlease set credentials via environment variables:")
            print('  $env:XMUOJ_USERNAME = "your_username"')
            print('  $env:XMUOJ_PASSWORD = "your_password"')
            print('  $env:XMUOJ_CONTEST_PASSWORD = "contest_password"')
            sys.exit(1)

    # Create output directory
    os.makedirs(config.output_dir, exist_ok=True)

    # Run
    if args.dry_run:
        success = asyncio.run(dry_run())
        sys.exit(0 if success else 1)
    elif args.single:
        asyncio.run(solve_single(args.single))
    else:
        asyncio.run(Orchestrator().run(limit=args.limit, problem_range=problem_range, problem_ids=problem_ids))


if __name__ == '__main__':
    main()

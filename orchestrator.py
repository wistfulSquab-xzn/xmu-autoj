"""
XMUOJ Auto Answer Orchestrator v2
Uses API-based submission (verified working) and Playwright for auth only.
"""
import asyncio
import json
import os
import random
import time
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import config
from auth import XMUOJAuth
from fetcher import ProblemFetcher, ProblemInfo
from ai_solver import AISolver, AIGeneratedCode


requests.packages.urllib3.disable_warnings()


def jitter(base: float, pct: float = 0.5) -> float:
    """Add random jitter to a delay: base ± pct%"""
    lo = base * (1 - pct)
    hi = base * (1 + pct)
    return max(0.5, random.uniform(lo, hi))


@dataclass
class ProblemAttempt:
    problem: ProblemInfo
    attempts: list = field(default_factory=list)
    solved: bool = False
    final_score: int = 0
    final_status: str = ""


@dataclass
class RunReport:
    contest_id: int = 0
    total_problems: int = 0
    solved: int = 0
    partial: int = 0
    failed: int = 0
    total_attempts: int = 0
    start_time: str = ""
    end_time: str = ""
    problems: list = field(default_factory=list)


class Orchestrator:
    """Main orchestrator using proven API submission approach."""

    def __init__(self):
        self.auth: Optional[XMUOJAuth] = None
        self.fetcher: Optional[ProblemFetcher] = None
        self.solver = AISolver(language=config.language)
        if not self.solver._valid:
            print("\n" + "=" * 60)
            print("  FATAL: AI 接口未就绪，无法继续")
            print("  请检查 .env 中的 API_KEY 和 API_BASE")
            print("=" * 60)
            return self.report
        self.report = RunReport()
        self.api_session: Optional[requests.Session] = None
        self.csrf_token: str = ""

    async def run(self, limit: int = None, problem_range: tuple = None,
                  problem_ids: list = None, contest_id: int = None) -> RunReport:
        if contest_id is not None:
            config.contest_id = contest_id
        self.report.contest_id = config.contest_id
        self.report.start_time = datetime.now().isoformat()

        print("=" * 70)
        print("  XMUOJ AUTO ANSWER v2")
        print(f"  Contest: {config.contest_id} | Model: {config.ai_model}")
        if problem_ids:
            print(f"  Target: {len(problem_ids)} specific problem(s)")
        elif problem_range:
            print(f"  Target: range {problem_range[0]}-{problem_range[1]}")
        print("=" * 70)

        try:
            # Phase 1: Login + get API credentials
            print("\n[1/5] Authentication...")
            self.auth = XMUOJAuth()
            if not await self.auth.login():
                print("FATAL: Login failed!")
                return self.report
            if not await self.auth.access_contest(config.contest_id):
                print("FATAL: Contest access failed!")
                return self.report
            print("[1/5] OK")

            # Setup API session with cookies from browser
            cookies = await self.auth.get_cookies_for_requests()
            self.csrf_token = cookies.get('csrftoken', '')
            self.api_session = requests.Session()
            self.api_session.cookies.update(cookies)
            self.api_session.verify = False
            self.api_session.headers.update({
                'X-CSRFToken': self.csrf_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            })

            # Validate AI API before doing any work
            print("\n[AI Check] Verifying API connectivity...")
            if not self.solver.validate():
                print("\n" + "=" * 60)
                print("  API 验证失败，已停止。请检查密钥后重试。")
                print("=" * 60)
                return self.report

            # Phase 2: Fetch problems via API
            print("\n[2/5] Fetching problems...")
            self.fetcher = ProblemFetcher()
            self.fetcher.set_cookies(cookies)
            problems = self.fetcher.get_contest_problems(config.contest_id)
            if problem_ids:
                # Filter by specific problem IDs (display_id or numeric id)
                id_set = set(str(p).upper() for p in problem_ids)
                matched = []
                skipped = []
                for p in problems:
                    if p.display_id.upper() in id_set or str(p.problem_id) in id_set:
                        matched.append(p)
                    else:
                        skipped.append(p)
                problems = matched
                if skipped:
                    print(f"[2/5] Matched {len(problems)} of {len(problem_ids)} specified problem(s)")
            elif problem_range:
                start, end = problem_range
                problems = problems[start-1:end]
                print(f"[2/5] Range: problems {start}-{end} ({len(problems)} problems)")
            elif limit:
                problems = problems[:limit]
                print(f"[2/5] Limited to first {limit} problems")
            self.report.total_problems = len(problems)
            print(f"[2/5] Found {len(problems)} problems")

            # Phase 3: Solve each problem
            print(f"\n[3/5] Solving {len(problems)} problem(s)...")
            results = []
            for i, problem in enumerate(problems):
                print(f"\n{'─' * 60}")
                print(f"  [{i+1}/{len(problems)}] {problem.display_id}: {problem.title}")
                print(f"{'─' * 60}")

                result = await self._solve_problem(problem)
                results.append(result)

                status = "OK" if result.solved else ("PARTIAL" if result.final_score > 0 else "FAIL")
                print(f"  {status} | Score: {result.final_score} | Attempts: {len(result.attempts)}")

                if i < len(problems) - 1:
                    time.sleep(jitter(config.delay_seconds * 2))  # longer pause between problems

            # Phase 4: Aggregate results
            print(f"\n[4/5] Aggregating results...")
            self.report.end_time = datetime.now().isoformat()
            self.report.problems = results
            for r in results:
                if r.solved:
                    self.report.solved += 1
                elif r.final_score > 0:
                    self.report.partial += 1
                else:
                    self.report.failed += 1
                self.report.total_attempts += len(r.attempts)

            # Phase 5: Report
            self._print_report()

        except Exception as e:
            print(f"\nFATAL: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.auth:
                await self.auth.close()

        return self.report

    async def _solve_problem(self, problem: ProblemInfo) -> ProblemAttempt:
        """Solve a single problem with API submission and result monitoring."""
        attempt_record = ProblemAttempt(problem=problem)
        previous_attempts = []

        for retry in range(config.max_retry_per_problem):
            print(f"\n  Attempt {retry + 1}/{config.max_retry_per_problem}")

            # 1. AI generates solution
            ai_result = self.solver.generate_solution(problem, previous_attempts)
            if not ai_result or not ai_result.code:
                print("  AI generation failed")
                continue

            print(f"  Code: {len(ai_result.code)} chars")

            # 2. Submit via API
            submission_id = self._api_submit(problem.problem_id, ai_result.code)
            if not submission_id:
                print("  Submit failed")
                attempt_record.attempts.append({
                    'attempt': retry + 1,
                    'status': 'Submit Failed',
                    'score': 0,
                })
                continue

            print(f"  Submitted: {submission_id}")

            # 3. Poll for result
            result = self._poll_result(submission_id)
            status = result.get('result', -1)
            score = result.get('statistic_info', {}).get('score', 0)
            time_cost = result.get('statistic_info', {}).get('time_cost', 0)
            mem_cost = result.get('statistic_info', {}).get('memory_cost', 0)

            # Map numeric result to status string
            # XMUOJ codes: 0=AC, 1=WA, 2=TLE, 3=MLE, 4=RE, 5=SE, 6=CE
            status_map = {0: 'Accepted', 1: 'Wrong Answer', 2: 'Time Limit Exceeded',
                         3: 'Memory Limit Exceeded', 4: 'Runtime Error',
                         5: 'System Error', 6: 'Compile Error'}
            status_str = status_map.get(status, f'Status({status})')

            # Check if really solved (result=0 means Accepted in XMUOJ)
            is_accepted = (status == 0)

            print(f"  Result: {status_str} | Score: {score} | Time: {time_cost}ms | Mem: {mem_cost//1024}KB")

            attempt_record.attempts.append({
                'attempt': retry + 1,
                'submission_id': submission_id,
                'status': status_str,
                'score': score,
                'time': f'{time_cost}ms',
                'memory': f'{mem_cost//1024}KB',
            })

            # Check if solved
            if is_accepted:
                attempt_record.solved = True
                attempt_record.final_score = score
                attempt_record.final_status = status_str
                print(f"  ACCEPTED! Score: {score}")
                break
            elif score >= 100:  # OI mode can have 100 without AC on all cases
                attempt_record.solved = True
                attempt_record.final_score = score
                attempt_record.final_status = status_str
                print(f"  PASSED! Score: {score}")
                break

            # Prepare for retry
            error_info = {
                'status': status_str,
                'error': str(result.get('info', {}))[:500],
                'score': score,
            }
            error_info['error'] += '\n' + self.solver.analyze_error(problem, error_info)
            previous_attempts.append(error_info)

            time.sleep(jitter(config.delay_seconds))

        # Set final state
        if attempt_record.attempts:
            last = attempt_record.attempts[-1]
            attempt_record.final_score = last.get('score', 0)
            attempt_record.final_status = last.get('status', 'Unknown')

        return attempt_record

    def _api_submit(self, problem_id: str, code: str) -> Optional[str]:
        """Submit code via XMUOJ API."""
        payload = {
            'problem_id': int(problem_id),
            'contest_id': config.contest_id,
            'code': code,
            'language': self.solver.submit_language,
        }

        r = self.api_session.post(
            f'{config.base_url}/api/submission',
            json=payload,
            headers={'Referer': f'{config.base_url}/problem/{problem_id}'},
            timeout=30,
        )

        if r.status_code != 200:
            print(f"  API error: {r.status_code}")
            return None

        data = r.json()
        if data.get('error'):
            print(f"  Submit error: {data.get('data')}")
            return None

        return data.get('data', {}).get('submission_id', '')

    def _poll_result(self, submission_id: str, max_wait: int = 60) -> dict:
        """Poll for submission result via API.
        XMUOJ result codes:
          -1 = Pending/Waiting
           0 = Accepted (FINAL)
           1 = Wrong Answer (FINAL)
           2 = Time Limit Exceeded (FINAL)
           3 = Memory Limit Exceeded (FINAL)
           4 = Runtime Error (FINAL)
           5 = System Error (FINAL)
           6 = Compiling → Compile Error (may be intermediate!)
           7 = Running/Judging (intermediate)
        """
        # These are truly final - won't change
        TRULY_FINAL = {0, 1, 2, 3, 4, 5}
        # These are always intermediate
        INTERMEDIATE = {-1, 7, 8}
        # result=6 is ambiguous: could be "Compiling" (intermediate)
        # or "Compile Error" (final). Need extra checks.

        start = time.time()
        last_result = None
        stable_since = 0

        while time.time() - start < max_wait:
            r = self.api_session.get(
                f'{config.base_url}/api/submission?id={submission_id}',
                timeout=10,
            )
            data = r.json().get('data', {})
            result_code = data.get('result', -1)
            score = data.get('statistic_info', {}).get('score', 0)
            info_err = data.get('info', {}).get('err')
            info_data = data.get('info', {}).get('data')

            # Truly final → return immediately
            if result_code in TRULY_FINAL:
                print(f"    (result={result_code}, score={score})")
                return data

            # Still intermediate → keep polling
            if result_code in INTERMEDIATE:
                if score != last_result:
                    print(f"    (judging... score={score})")
                    last_result = score
                time.sleep(jitter(config.poll_interval))
                continue

            # result=6: need to distinguish "still compiling" vs "compile error"
            if result_code == 6:
                # Real compile error: info.err has a message
                if info_err:
                    print(f"    (compile error detected)")
                    return data
                # Has test results → might be a weird state, check if stable
                if info_data and len(info_data) > 0:
                    # Check if this state is stable (same result for 3 polls)
                    state_key = (result_code, score, len(info_data))
                    if state_key == last_result:
                        stable_since += 1
                        if stable_since >= 3:
                            print(f"    (result=6 stable, treating as final)")
                            return data
                    else:
                        stable_since = 0
                        last_result = state_key
                        print(f"    (compiling... test_cases={len(info_data)})")
                else:
                    print(f"    (compiling...)")

                time.sleep(jitter(config.poll_interval))
                continue

            # Unknown code → wait and see
            print(f"    (unknown result={result_code})")
            time.sleep(jitter(config.poll_interval))

        # Timeout
        print("    (timeout)")
        r = self.api_session.get(
            f'{config.base_url}/api/submission?id={submission_id}',
            timeout=10,
        )
        return r.json().get('data', {})

    def _print_report(self):
        """Print final report."""
        print("\n" + "=" * 70)
        print("  FINAL REPORT")
        print("=" * 70)
        print(f"  Contest: {config.contest_id}")
        print(f"  Problems: {self.report.total_problems}")
        print(f"  Solved: {self.report.solved}")
        print(f"  Partial: {self.report.partial}")
        print(f"  Failed: {self.report.failed}")
        print(f"  Total attempts: {self.report.total_attempts}")
        success_rate = 100 * self.report.solved / max(1, self.report.total_problems)
        print(f"  Success rate: {success_rate:.1f}%")
        print("-" * 70)
        for p in self.report.problems:
            icon = "OK" if p.solved else ("~" if p.final_score > 0 else "FAIL")
            print(f"  {icon:4s} {p.problem.display_id:8s} {p.problem.title[:35]:35s} "
                  f"Score: {p.final_score:3d}  Attempts: {len(p.attempts)}")
        print("=" * 70)

        # Save JSON report
        os.makedirs(config.output_dir, exist_ok=True)
        report_file = os.path.join(config.output_dir, "report.json")
        report_data = {
            'contest_id': self.report.contest_id,
            'start_time': self.report.start_time,
            'end_time': self.report.end_time,
            'total_problems': self.report.total_problems,
            'solved': self.report.solved,
            'partial': self.report.partial,
            'failed': self.report.failed,
            'total_attempts': self.report.total_attempts,
            'problems': [
                {
                    'problem_id': p.problem.problem_id,
                    'display_id': p.problem.display_id,
                    'title': p.problem.title,
                    'solved': p.solved,
                    'final_score': p.final_score,
                    'final_status': p.final_status,
                    'attempts': p.attempts,
                }
                for p in self.report.problems
            ],
        }
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"\n  Report saved to {report_file}")


async def main():
    try:
        config.validate()
    except ValueError as e:
        print(f"Config error: {e}")
        print("Set env vars: XMUOJ_USERNAME, XMUOJ_PASSWORD, XMUOJ_CONTEST_PASSWORD")
        return

    orchestrator = Orchestrator()
    await orchestrator.run()


if __name__ == '__main__':
    asyncio.run(main())

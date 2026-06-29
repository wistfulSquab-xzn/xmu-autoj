#!/usr/bin/env python3
"""
XMUOJ 自动答题 - 傻瓜式启动器
  双击 启动.bat 或运行 python start.py 即可
"""
import os, sys, asyncio, re

from config import config
from orchestrator import Orchestrator


def _extract_contest_id(raw: str) -> int:
    """从用户输入中提取比赛ID，支持各种URL格式。

    正确提取示例：
      https://xmuoj.com/contest/361/problems    → 361
      https://xmuoj.com/contest/361/announcements → 361
      xmuoj.com/contest/361/ann                 → 361
      https://xmuoj.com/contest/361/problem/JD002 → 361
      361                                       → 361
    """
    raw = raw.strip()
    # 匹配 /contest/{数字} 模式，无论前后是什么
    m = re.search(r'/contest/(\d+)', raw)
    if m:
        return int(m.group(1))
    # 纯数字输入
    m = re.search(r'^\s*(\d+)\s*$', raw)
    if m:
        return int(m.group(1))
    # 无法识别，报错
    print(f"  ✗ 无法从输入中识别比赛ID: {raw}")
    print(f"  请输入比赛网址（如 https://xmuoj.com/contest/361）或纯数字ID")
    sys.exit(1)


def _ensure_env():
    """确保 .env 存在，不存在则引导用户创建。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        # 重新加载确保最新
        from config import _load_dotenv
        _load_dotenv()
        config.username = os.getenv("XMUOJ_USERNAME", "")
        config.password = os.getenv("XMUOJ_PASSWORD", "")
        config.contest_password = os.getenv("XMUOJ_CONTEST_PASSWORD", "")
        if config.username and config.password:
            return True

    print()
    print("首次使用 - 设置凭据")
    print()
    print("  [XMUOJ 登录]")
    username = input("  学号/用户名: ").strip()
    password = input("  密码: ").strip()
    contest_pw = input("  比赛密码 (直接回车=ilovexmu): ").strip() or "ilovexmu"
    print()
    print("  [AI 密钥]")
    print("  本工具使用 DeepSeek 生成代码，需 API 密钥")
    print("  获取: https://platform.deepseek.com → 注册 → API Keys")
    ds_key = input("  DeepSeek API Key (sk-...): ").strip()

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f'XMUOJ_USERNAME={username}\n')
        f.write(f'XMUOJ_PASSWORD={password}\n')
        f.write(f'XMUOJ_CONTEST_PASSWORD={contest_pw}\n')
        if ds_key:
            f.write(f'DEEPSEEK_API_KEY={ds_key}\n')

    config.username = username
    config.password = password
    config.contest_password = contest_pw
    print(f"  ✓ 已保存 (用户: {username})")
    print()
    return True


def _pick_problems():
    """让用户选择题目的方式。"""
    print("  ──────────────────────────────")
    print("  怎么选题？")
    print("   [1] 全部题目")
    print("   [2] 指定区间，如 12-30")
    print("   [3] 指定题目，如 JD027,JD029,7318")
    print("   [4] 只做前N题")
    choice = input("  请选择: ").strip() or "1"

    if choice == "1":
        return {"mode": "all"}
    elif choice == "2":
        r = input("  区间 (如 27-40): ").strip()
        parts = r.split("-")
        if len(parts) == 2:
            return {"mode": "range", "start": int(parts[0]), "end": int(parts[1])}
        else:
            print("  格式错误，使用全部题目")
            return {"mode": "all"}
    elif choice == "3":
        ids = input("  题目ID，逗号分隔 (如 JD027,JD029,7318): ").strip()
        return {"mode": "ids", "ids": [p.strip() for p in ids.split(",") if p.strip()]}
    elif choice == "4":
        n = input("  做前几题 (如 5): ").strip()
        return {"mode": "limit", "limit": int(n) if n.isdigit() else 5}
    else:
        return {"mode": "all"}


def main():
    print()

    print("XMUOJ 自动答题    by苦涩乳鸽")


    # 1. 确保有凭据
    _ensure_env()

    # 2. 选择比赛
    print("  ──────────────────────────────")
    raw = input("  输入比赛网址或ID: ").strip()
    config.contest_id = _extract_contest_id(raw)
    print(f"  识别到比赛ID: {config.contest_id}")

    # 3. 选择题
    pick = _pick_problems()

    problem_range = None
    problem_ids = None
    limit = None

    if pick["mode"] == "range":
        problem_range = (pick["start"], pick["end"])
        desc = f"第{pick['start']}-{pick['end']}题"
    elif pick["mode"] == "ids":
        problem_ids = pick["ids"]
        desc = f"{len(problem_ids)}道指定题"
    elif pick["mode"] == "limit":
        limit = pick["limit"]
        desc = f"前{limit}题"
    else:
        desc = "全部题目"

    # 4. 确认
    print()
    print(f"  ──────────────────────────────")
    print(f"  比赛: {config.contest_id}")
    print(f"  选题: {desc}")
    print(f"  每题最多重试: {config.max_retry_per_problem}次")
    ok = input("  确认开始? [Y/n]: ").strip().lower()
    if ok and ok != "y":
        print("  已取消")
        return

    # 5. 开跑
    asyncio.run(Orchestrator().run(
        limit=limit,
        problem_range=problem_range,
        problem_ids=problem_ids,
    ))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  已中断")
    except Exception as e:
        print(f"\n  错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n  按回车退出...")

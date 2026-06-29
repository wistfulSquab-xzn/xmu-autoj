#!/usr/bin/env python3
"""XMUOJ 自动答题 - 双击 启动.bat 即可"""
import os, sys, asyncio, re

from config import config
from orchestrator import Orchestrator


def _mask(s: str) -> str:
    if not s: return "(未设置)"
    if len(s) <= 6: return "*" * len(s)
    return s[:3] + "***" + s[-3:]


def _extract_contest_id(raw: str) -> int:
    m = re.search(r'/contest/(\d+)', raw)
    if m: return int(m.group(1))
    m = re.search(r'^\s*(\d+)\s*$', raw)
    if m: return int(m.group(1))
    print(f"  无法识别比赛ID: {raw}")
    sys.exit(1)


def _ensure_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        from config import _load_dotenv
        _load_dotenv()
        config.username = os.getenv("XMUOJ_USERNAME", "")
        config.password = os.getenv("XMUOJ_PASSWORD", "")
        config.contest_password = os.getenv("XMUOJ_CONTEST_PASSWORD", "")
        if config.username and config.password:
            api = os.getenv("API_KEY", "")
            print(f"  用户: {config.username}")
            print(f"  密码: {_mask(config.password)}")
            print(f"  API Key: {_mask(api)}")
            print(f"  是否修改以上凭据?")
            print(f"  [1] 不修改（默认选项，回车即可）")
            print(f"  [2] 修改")
            chg = input("  选择: ").strip()
            if chg != "2":
                return
        print()

    if not os.path.exists(env_path):
        print("  首次使用 - 设置凭据")
    print()
    config.username = input(f"  学号 [{config.username or '必填'}]: ").strip() or config.username
    config.password = input(f"  密码 [{_mask(config.password)}]: ").strip() or config.password
    config.contest_password = input(f"  比赛密码 [{config.contest_password or 'ilovexmu'}]: ").strip() or config.contest_password or "ilovexmu"

    print()
    print("  AI 密钥（获取: platform.deepseek.com → API Keys）")
    current_key = os.getenv("API_KEY", "")
    api_key = input(f"  API Key [{_mask(current_key)}]: ").strip()
    if not api_key:
        api_key = current_key

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f'XMUOJ_USERNAME={config.username}\n')
        f.write(f'XMUOJ_PASSWORD={config.password}\n')
        f.write(f'XMUOJ_CONTEST_PASSWORD={config.contest_password}\n')
        if api_key:
            f.write(f'API_KEY={api_key}\n')
            f.write(f'API_BASE=https://api.deepseek.com/v1\n')
            f.write(f'API_MODEL=deepseek-v4-pro\n')

    print("  已保存")
    print()


def _pick_problems():
    print("  选题方式:")
    print("  [1] 全部题目 (默认选项，回车即可)")
    print("  [2] 指定区间（如 12-30）")
    print("  [3] 指定题目（如 JD027,JD029）")
    print("  [4] 只做前N题")
    choice = input("  选择: ").strip() or "1"

    if choice == "1":
        return {"mode": "all"}
    elif choice == "2":
        r = input("  区间 (如 27-40): ").strip()
        parts = r.split("-")
        if len(parts) == 2:
            return {"mode": "range", "start": int(parts[0]), "end": int(parts[1])}
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
    print("  ╔══════════════════════════════════╗")
    print("  ║   XMUOJ 自动答题  by苦涩乳鸽    ║")
    print("  ╚══════════════════════════════════╝")
    print()

    # 1. 凭据
    _ensure_env()

    # 2. 网址
    raw = input("  粘贴比赛网址: ").strip()
    cid = _extract_contest_id(raw)
    config.contest_id = cid
    print(f"  → 比赛 {cid}")

    # 3. 选题
    print()
    parsed = _pick_problems()

    problem_range = None; problem_ids = None; limit = None
    if parsed["mode"] == "all":
        desc = "全部"
    elif parsed["mode"] == "range":
        problem_range = (parsed["start"], parsed["end"])
        desc = f"第{parsed['start']}-{parsed['end']}题"
    elif parsed["mode"] == "ids":
        problem_ids = parsed["ids"]
        desc = f"{len(problem_ids)}道: {', '.join(problem_ids)}"
    elif parsed["mode"] == "limit":
        limit = parsed["limit"]
        desc = f"前{limit}题"

    # 4. 语言
    print()
    print("  输出语言:")
    print("  [1] C++ (默认选项，回车即可)")
    print("  [2] C")
    print("  [3] Python3")
    print("  [4] Java")
    lang_choice = input("  选择: ").strip() or "1"
    config.language = {"1": "cpp", "2": "c", "3": "python", "4": "java"}.get(lang_choice, "cpp")

    # 5. 延时
    print()
    print("  延时设置（防封号）:")
    print("  [1] 快速 (0.5s，有风险)")
    print("  [2] 正常 (3s，默认选项，回车即可)")
    print("  [3] 安全 (8s)")
    d_choice = input("  选择: ").strip() or "2"
    config.delay_seconds = {"1": 0.5, "2": 3.0, "3": 8.0}.get(d_choice, 3.0)

    # 6. 确认
    lang_names = {"cpp": "C++", "c": "C", "python": "Python3", "java": "Java"}
    delay_names = {0.5: "快速", 3.0: "正常", 8.0: "安全"}
    print()
    print("  ─────────────────────────────")
    print(f"  比赛 {cid} | {lang_names.get(config.language, config.language)} | {desc}")
    print(f"  延时 {delay_names.get(config.delay_seconds, str(config.delay_seconds))} | 重试{config.max_retry_per_problem}次")
    print()
    ok = input("  回车开始 [Enter]: ").strip().lower()
    if ok and ok not in ('y', 'yes', ''):
        print("  已取消")
        return

    # 7. 开跑
    asyncio.run(Orchestrator().run(
        limit=limit, problem_range=problem_range, problem_ids=problem_ids,
    ))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n  已中断")
    except Exception as e:
        print(f"\n  错误: {e}")
        import traceback; traceback.print_exc()
    finally:
        input("\n  按回车退出...")

"""Environment checker - auto-installs missing dependencies."""
import subprocess, sys, os


def main():
    print()
    print("  XMUOJ Auto Answer - Setup Check")
    print("  " + "-" * 34)

    ok = True

    # 1. Python version
    v = sys.version_info
    if v < (3, 8):
        print(f"  ERROR: Python {v.major}.{v.minor} too old, need 3.8+")
        print("  Download: https://www.python.org/downloads/")
        return
    print(f"  Python {v.major}.{v.minor}.{v.micro}")

    # 2. pip packages (requests is transitive but check explicitly)
    pkgs = [
        ("playwright", "playwright"),
        ("beautifulsoup4", "bs4"),
        ("anthropic", "anthropic"),
        ("openai", "openai"),
        ("requests", "requests"),
    ]
    for pkg, imp in pkgs:
        try:
            __import__(imp)
        except ImportError:
            print(f"  Installing {pkg}...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                print(f"  FAILED: pip install {pkg}")
                if r.stderr:
                    print(f"    {r.stderr.strip()[-200:]}")
                ok = False
            else:
                print(f"    done")
    print("  Packages OK")

    # 3. Playwright browser
    try:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        try:
            p.chromium.launch()
            print("  Browser OK")
        except Exception:
            print("  Downloading browser (~180MB, mirror)...")
            env = os.environ.copy()
            env["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright/"
            r = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, env=env
            )
            if r.returncode != 0:
                print("  WARNING: Browser download failed!")
                if r.stderr:
                    print(f"    {r.stderr.strip()[-300:]}")
                print("  Try manually: playwright install chromium")
                ok = False
            else:
                # Verify install
                try:
                    p.chromium.launch()
                    print("  Browser OK")
                except Exception as e2:
                    print(f"  WARNING: Browser installed but won't launch: {e2}")
                    ok = False
        finally:
            p.stop()
    except ImportError:
        print("  SKIP: playwright not installed (packages failed)")
        ok = False
    except Exception as e:
        print(f"  WARNING: Browser check failed: {e}")
        ok = False

    print()
    if ok:
        print("  All OK! Ready to use.")
    else:
        print("  Some checks failed. Fix issues above then retry.")
    print()


if __name__ == "__main__":
    main()

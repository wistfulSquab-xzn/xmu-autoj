"""Environment checker - auto-installs missing dependencies."""
import subprocess, sys, os

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, shell=True)

def check_pip_pkg(name, import_name=None):
    """Check if a pip package is installed, auto-install if missing."""
    if import_name is None:
        import_name = name
    try:
        __import__(import_name)
        return True
    except ImportError:
        print(f"  Installing {name}...")
        r = run(f"{sys.executable} -m pip install {name} -q")
        if r.returncode != 0:
            print(f"  WARNING: Failed to install {name}")
            print(f"  Run manually: pip install {name}")
            return False
        return True

def main():
    print()
    print("  XMUOJ Auto Answer - Setup Check")
    print("  " + "-" * 34)

    ok = True

    # Check pip packages
    for pkg, imp in [("playwright", "playwright"), ("beautifulsoup4", "bs4"),
                      ("anthropic", "anthropic"), ("openai", "openai")]:
        if not check_pip_pkg(pkg, imp):
            ok = False

    # Check Playwright browser (use Chinese mirror for faster download)
    try:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        try:
            p.chromium.launch()
        except Exception:
            print("  Downloading browser (~180MB, using mirror)...")
            # Use npmmirror (Chinese CDN) for faster download
            env = os.environ.copy()
            env["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright/"
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, env=env
            )
        finally:
            p.stop()
    except Exception as e:
        print(f"  WARNING: Browser check failed: {e}")
        ok = False

    if ok:
        print("  All OK!")
    print()

if __name__ == "__main__":
    main()

"""
XMUOJ Authentication Module
XMUOJ uses QingdaoU/OnlineJudge (SPA with iView UI).
Login is a modal dialog on the homepage, not a separate page.
"""
import json
import os
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import config


class XMUOJAuth:
    """Handles XMUOJ authentication using Playwright."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self._cookies_path = os.path.join(config.output_dir, config.cookies_file)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _init_browser(self):
        """Initialize Playwright browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ],
        )
        self.context = await self.browser.new_context(
            ignore_https_errors=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(config.browser_timeout)

    async def login(self) -> bool:
        """
        Log into XMUOJ. The login is a modal dialog on the homepage.
        Returns True if login successful, False otherwise.
        """
        await self._init_browser()

        # Try to load saved cookies first (with timeout protection)
        cookie_login_ok = False
        if os.path.exists(self._cookies_path):
            print("[Auth] Loading saved cookies...")
            try:
                with open(self._cookies_path, 'r') as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                # Use a shorter timeout for cookie validation
                await self.page.goto(config.base_url, timeout=15000)
                await asyncio.sleep(3)
                # Check if logged in
                login_btn = await self.page.query_selector('button:has-text("登录")')
                if not login_btn:
                    print("[Auth] Cookies valid — already logged in!")
                    cookie_login_ok = True
                    return True
                print("[Auth] Cookies expired, re-logging in...")
            except Exception as e:
                print(f"[Auth] Cookie load failed ({e}), doing fresh login...")
                # Delete bad cookies file
                try:
                    os.remove(self._cookies_path)
                except:
                    pass

        # Navigate to homepage (SPA entry point)
        print("[Auth] Loading homepage...")
        await self.page.goto(config.base_url, wait_until='domcontentloaded')

        # Wait for SPA to render (Vue.js needs time to bootstrap)
        print("[Auth] Waiting for SPA to render...")
        login_btn = None
        for attempt in range(10):
            await asyncio.sleep(2)
            login_btn = await self._find_element([
                'button:has-text("登录")',
                'button.ivu-btn-ghost',
                'button.ivu-btn-circle',
            ])
            if login_btn:
                break
            print(f"    waiting... ({attempt+1})")

        if not login_btn:
            # Fallback: try any button in header
            header_btns = await self.page.query_selector_all('header button, nav button, .ivu-layout-header button')
            if header_btns:
                login_btn = header_btns[0]

        if not login_btn:
            print("[Auth] ERROR: Cannot find login button!")
            await self.page.screenshot(path=os.path.join(config.output_dir, 'auth_error.png'))
            print("[Auth] Screenshot saved to output/auth_error.png")
            return False

        await login_btn.click()
        await asyncio.sleep(2)

        # Fill in login modal
        print("[Auth] Filling credentials...")
        username_input = await self._find_element([
            'input[placeholder*="用户"]',
            'input[placeholder*="用户名"]',
            'input[type="text"]',
        ])
        password_input = await self._find_element([
            'input[placeholder*="密码"]',
            'input[type="password"]',
        ])

        if not username_input or not password_input:
            print("[Auth] ERROR: Could not find login inputs in modal!")
            # Debug: take screenshot
            await self.page.screenshot(path=os.path.join(config.output_dir, 'login_error.png'))
            print("[Auth] Screenshot saved to output/login_error.png")
            return False

        await username_input.fill(config.username)
        await asyncio.sleep(0.5)
        await password_input.fill(config.password)

        # Submit login — try multiple approaches
        print("[Auth] Submitting login...")

        # Method 1: Press Enter in password field
        await password_input.press('Enter')
        await asyncio.sleep(4)

        # Method 2: If modal still visible, force-click the submit button
        modal_visible = await self.page.query_selector('.ivu-modal-wrap')
        if modal_visible:
            print("[Auth] Modal still open, trying force click...")
            # Find the primary button in the modal
            modal_btn = await self.page.query_selector(
                '.ivu-modal-wrap button.ivu-btn-primary, '
                '.ivu-modal button.ivu-btn-primary'
            )
            if modal_btn:
                await modal_btn.click(force=True)
                await asyncio.sleep(4)
            else:
                # Try any button with 登录 text
                all_btns = await self.page.query_selector_all('button')
                for btn in all_btns:
                    text = (await btn.inner_text()).strip()
                    if '登录' in text or 'Login' in text or 'Sign' in text:
                        await btn.click(force=True)
                        await asyncio.sleep(4)
                        break

        # Verify login success
        await self.page.goto(config.base_url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        print(f"[Auth] After login URL: {self.page.url}")

        # Check: login button should be gone, user should be visible
        login_btn = await self.page.query_selector('button:has-text("登录")')
        user_menu = await self.page.query_selector('.ivu-avatar, .user-menu, [class*=user]')

        if login_btn and not user_menu:
            print("[Auth] Login may have failed — checking for error...")
            error_el = await self.page.query_selector('.ivu-message-error, [class*=error]')
            if error_el:
                try:
                    error_text = (await error_el.inner_text()).strip()
                    print(f"[Auth] Login error: {error_text}")
                except:
                    pass
            # Take screenshot for debugging
            await self.page.screenshot(path=os.path.join(config.output_dir, 'login_failed.png'))
            print("[Auth] Screenshot saved to output/login_failed.png")
            return False

        print("[Auth] Login successful!")
        # Save cookies
        cookies = await self.context.cookies()
        os.makedirs(os.path.dirname(self._cookies_path), exist_ok=True)
        with open(self._cookies_path, 'w') as f:
            json.dump(cookies, f)
        print(f"[Auth] Cookies saved to {self._cookies_path}")
        return True

    async def access_contest(self, contest_id: int = None) -> bool:
        """
        Access a password-protected contest.
        XMUOJ uses client-side routing, so navigate from the SPA.
        """
        if contest_id is None:
            contest_id = config.contest_id

        contest_url = f"{config.base_url}/contest/{contest_id}"
        print(f"[Auth] Navigating to contest {contest_id}...")

        # Navigate directly (SPA handles routing)
        await self.page.goto(contest_url, wait_until='domcontentloaded')
        await asyncio.sleep(4)

        current_url = self.page.url
        print(f"[Auth] Contest page URL: {current_url}")

        # Check if we got redirected to homepage (needs login)
        if current_url.rstrip('/') == config.base_url.rstrip('/'):
            print("[Auth] Redirected to homepage — session may be expired")
            return False

        # Check for password dialog (iView modal)
        password_input = await self._find_element([
            'input[type="password"]',
            '.ivu-modal input[type="password"]',
            'input[placeholder*="密码"]',
        ])

        if password_input:
            print("[Auth] Contest is password protected. Entering password...")
            await password_input.fill(config.contest_password)
            await asyncio.sleep(0.5)
            # Press Enter first (most reliable)
            await password_input.press('Enter')
            await asyncio.sleep(4)

            # Check if password dialog is still visible
            pw_still = await self.page.query_selector('.ivu-modal input[type="password"]')
            if pw_still:
                # Try force-click the confirm button
                confirm_btn = await self.page.query_selector(
                    '.ivu-modal-wrap button.ivu-btn-primary, '
                    '.ivu-modal button.ivu-btn-primary'
                )
                if confirm_btn:
                    await confirm_btn.click(force=True)
                    await asyncio.sleep(4)
                    print(f"[Auth] Clicked confirm. URL: {self.page.url}")
                else:
                    print("[Auth] WARNING: Confirm button not found after password")

        # Verify access
        current_url = self.page.url
        if f'/contest/{contest_id}' in current_url:
            print(f"[Auth] Successfully accessed contest {contest_id}!")
            return True

        print(f"[Auth] Could not access contest {contest_id}")
        return False

    async def _find_element(self, selectors: list[str]):
        """Try multiple selectors to find an element."""
        for sel in selectors:
            el = await self.page.query_selector(sel)
            if el:
                return el
        return None

    async def get_cookies_for_requests(self) -> dict:
        """Get cookies in dict format for use with requests library."""
        cookies = await self.context.cookies()
        return {c['name']: c['value'] for c in cookies}

    async def close(self):
        """Close browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

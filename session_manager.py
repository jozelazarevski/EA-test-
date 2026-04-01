"""
Session Manager — Persists Playwright browser sessions across runs.

Uses Playwright's storage_state API to save/restore cookies, localStorage,
and sessionStorage so users don't have to re-authenticate via OTP every time.

Workflow:
  1. First run: user logs in manually → session saved to disk.
  2. Subsequent runs: session loaded from disk → login skipped.
  3. If saved session is expired/invalid → falls back to manual login,
     then saves the new session.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)

# Default location for the persisted session file
_DEFAULT_SESSION_DIR = Path(__file__).parent / ".session"
_DEFAULT_SESSION_FILE = _DEFAULT_SESSION_DIR / "auth_state.json"

# How long a saved session is considered fresh before we re-validate
_SESSION_MAX_AGE_HOURS = 12


class SessionManager:
    """Manages Playwright session persistence for Expert Advisor auth."""

    def __init__(
        self,
        session_dir: str | Path | None = None,
        max_age_hours: float = _SESSION_MAX_AGE_HOURS,
    ) -> None:
        self.session_dir = Path(session_dir) if session_dir else _DEFAULT_SESSION_DIR
        self.session_file = self.session_dir / "auth_state.json"
        self.max_age_hours = max_age_hours
        self.session_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_saved_session(self) -> bool:
        """Check if a saved session file exists and is not too old."""
        if not self.session_file.exists():
            return False
        return not self._is_expired()

    async def load_into_context(self, context: BrowserContext) -> bool:
        """
        Load saved cookies/storage into an existing browser context.

        Returns True if a session was loaded, False otherwise.
        """
        if not self.has_saved_session():
            logger.info("No valid saved session found")
            return False

        try:
            state = self._read_state()
            cookies = state.get("cookies", [])
            if cookies:
                await context.add_cookies(cookies)
                logger.info("Loaded %d cookies from saved session", len(cookies))

            # localStorage/sessionStorage can only be set after navigation,
            # so we store them for later injection via _inject_storage().
            self._pending_origins = state.get("origins", [])
            return True
        except Exception as exc:
            logger.warning("Failed to load saved session: %s", exc)
            return False

    async def inject_storage(self, page: Page) -> None:
        """
        Inject localStorage/sessionStorage into the current page.

        Call this AFTER page.goto() so we have access to the page's origin.
        """
        origins = getattr(self, "_pending_origins", [])
        if not origins:
            return

        for origin_data in origins:
            local_items = origin_data.get("localStorage", [])
            session_items = origin_data.get("sessionStorage", [])

            for item in local_items:
                try:
                    await page.evaluate(
                        "(item) => localStorage.setItem(item.name, item.value)",
                        item,
                    )
                except Exception:
                    pass  # Cross-origin or page not ready — non-fatal

            for item in session_items:
                try:
                    await page.evaluate(
                        "(item) => sessionStorage.setItem(item.name, item.value)",
                        item,
                    )
                except Exception:
                    pass

        logger.info("Injected storage for %d origin(s)", len(origins))
        self._pending_origins = []

    async def save_from_context(self, context: BrowserContext) -> Path:
        """
        Capture cookies + storage from the current context and save to disk.

        Returns the path to the saved session file.
        """
        try:
            state = await context.storage_state()
            self._write_state(state)
            cookie_count = len(state.get("cookies", []))
            logger.info(
                "Session saved: %d cookies → %s",
                cookie_count, self.session_file,
            )
            return self.session_file
        except Exception as exc:
            logger.error("Failed to save session: %s", exc)
            raise

    async def validate_session(self, page: Page, target_url: str) -> bool:
        """
        Check if the current page is actually authenticated.

        Navigates to the target URL and looks for signs of a logged-in state
        (presence of the chat input) vs a login/auth page.

        Args:
            page: The Playwright page.
            target_url: The EA app URL.

        Returns:
            True if the session is authenticated, False if login is needed.
        """
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
        except Exception as exc:
            logger.warning("Navigation failed during session validation: %s", exc)
            return False

        # Signs of being logged in: presence of the chat input
        authenticated_selectors = [
            "textarea",
            "input[type='text']",
            "[contenteditable='true']",
            "[placeholder*='ask']",
            "[placeholder*='Ask']",
            "[placeholder*='question']",
            "[placeholder*='message']",
            "[placeholder*='Message']",
            "[role='textbox']",
        ]

        for selector in authenticated_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                logger.info("Session is valid — chat input found: %s", selector)
                return True
            except Exception:
                continue

        # Signs of NOT being logged in: login form, OTP page, etc.
        login_indicators = [
            "input[type='password']",
            "[placeholder*='OTP']",
            "[placeholder*='otp']",
            "[placeholder*='code']",
            "[placeholder*='email']",
            "[placeholder*='username']",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "button:has-text('Login')",
            "text=Sign in",
            "text=Log in",
        ]

        for selector in login_indicators:
            try:
                el = await page.query_selector(selector)
                if el:
                    logger.info("Session expired — login page detected: %s", selector)
                    return False
            except Exception:
                continue

        # Ambiguous — assume not authenticated to be safe
        logger.warning("Session validation inconclusive — assuming expired")
        return False

    async def wait_for_manual_login(
        self,
        page: Page,
        target_url: str,
        timeout: float = 300,
    ) -> bool:
        """
        Wait for the user to complete manual login (OTP).

        Polls every 3 seconds to check if the chat input appears.
        Prints instructions to the console.

        Args:
            page: The Playwright page (should be on the login page).
            target_url: The EA app URL.
            timeout: Maximum time to wait in seconds (default 5 minutes).

        Returns:
            True if login was detected, False if timed out.
        """
        print("\n" + "=" * 60)
        print("  Manual Login Required")
        print("=" * 60)
        print(f"  Please log in to Expert Advisor in the browser window.")
        print(f"  Complete the OTP authentication process.")
        print(f"  Waiting up to {int(timeout)}s for login to complete...")
        print("=" * 60 + "\n")

        start = time.time()
        poll_interval = 3.0

        while time.time() - start < timeout:
            # Check if we've landed on the authenticated app
            authenticated_selectors = [
                "textarea",
                "input[type='text']:not([type='password'])",
                "[contenteditable='true']",
                "[placeholder*='ask']",
                "[placeholder*='Ask']",
                "[placeholder*='question']",
                "[placeholder*='message']",
                "[role='textbox']",
            ]

            for selector in authenticated_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        elapsed = int(time.time() - start)
                        print(f"\n[Session] Login detected after {elapsed}s!")
                        return True
                except Exception:
                    continue

            await page.wait_for_timeout(poll_interval * 1000)

        print("\n[Session] Login timed out.")
        return False

    def clear(self) -> None:
        """Delete the saved session file."""
        if self.session_file.exists():
            self.session_file.unlink()
            logger.info("Cleared saved session: %s", self.session_file)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _read_state(self) -> dict[str, Any]:
        with open(self.session_file) as f:
            return json.load(f)

    def _write_state(self, state: dict[str, Any]) -> None:
        # Add metadata
        state["_saved_at"] = time.time()
        state["_saved_at_human"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.session_file, "w") as f:
            json.dump(state, f, indent=2)

    def _is_expired(self) -> bool:
        """Check if the saved session is older than max_age_hours."""
        try:
            state = self._read_state()
            saved_at = state.get("_saved_at", 0)
            age_hours = (time.time() - saved_at) / 3600
            if age_hours > self.max_age_hours:
                logger.info(
                    "Saved session is %.1f hours old (max: %.1f) — expired",
                    age_hours, self.max_age_hours,
                )
                return True
            return False
        except Exception:
            return True

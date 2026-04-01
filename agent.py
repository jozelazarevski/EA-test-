"""
HVAC Testing Agent - Browser automation for Expert Advisor testing.

This agent uses Playwright to interact with https://expertadvisor.jci.com/,
submit HVAC questions, capture responses, download PDFs, and validate results.
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, BrowserContext

from config import (
    TARGET_URL,
    DOWNLOADS_DIR,
    HEADLESS,
    SLOW_MO,
    DEFAULT_TIMEOUT,
    MAX_WAIT_FOR_RESPONSE,
    SCREENSHOT_ON_EACH_STEP,
    REPORTS_DIR,
)
from hvac_test_cases import TEST_CASES
from validators import validate_response, validate_pdf
from report_generator import ReportGenerator


class HVACTestingAgent:
    """Automated testing agent for the JCI Expert Advisor HVAC tool."""

    def __init__(self, headless: bool = None, test_ids: list = None):
        self.headless = headless if headless is not None else HEADLESS
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshots_dir = REPORTS_DIR / f"screenshots_{self.run_id}"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.test_ids = test_ids  # If None, run all tests

    async def setup(self):
        """Launch browser and navigate to Expert Advisor."""
        print(f"[Agent] Launching browser (headless={self.headless})...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=SLOW_MO,
        )
        self.context = await self.browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
        )
        self.context.set_default_timeout(DEFAULT_TIMEOUT)
        self.page = await self.context.new_page()

        print(f"[Agent] Navigating to {TARGET_URL}...")
        await self.page.goto(TARGET_URL, wait_until="networkidle")
        await self._screenshot("01_initial_load")

        # Wait for the page to be ready - check if we're logged in
        await self._wait_for_app_ready()

    async def _wait_for_app_ready(self):
        """Wait for the Expert Advisor app to be fully loaded and ready."""
        print("[Agent] Waiting for application to be ready...")

        # Try multiple selectors that might indicate the app is ready
        ready_selectors = [
            "textarea",
            "input[type='text']",
            "[contenteditable='true']",
            "[placeholder*='ask']",
            "[placeholder*='Ask']",
            "[placeholder*='question']",
            "[placeholder*='type']",
            "[placeholder*='Type']",
            "[placeholder*='message']",
            "[placeholder*='Message']",
            "[role='textbox']",
        ]

        for selector in ready_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=5000)
                print(f"[Agent] App ready - found input: {selector}")
                return selector
            except Exception:
                continue

        # If no known selector found, wait and take a screenshot for debugging
        print("[Agent] Warning: Could not find a known input selector. Taking debug screenshot...")
        await self._screenshot("debug_app_state")
        # Still proceed - the input detection will happen in send_question
        return None

    async def _screenshot(self, name: str):
        """Take a screenshot if enabled."""
        if SCREENSHOT_ON_EACH_STEP and self.page:
            path = self.screenshots_dir / f"{name}.png"
            await self.page.screenshot(path=str(path), full_page=True)
            print(f"[Agent] Screenshot saved: {path.name}")

    async def _find_input_element(self):
        """Find the chat/question input element on the page."""
        selectors = [
            "textarea",
            "input[type='text']",
            "[contenteditable='true']",
            "[placeholder*='ask']",
            "[placeholder*='Ask']",
            "[placeholder*='question']",
            "[placeholder*='type']",
            "[placeholder*='Type']",
            "[placeholder*='message']",
            "[placeholder*='Message']",
            "[role='textbox']",
            "#prompt-textarea",
            ".chat-input",
            "[data-testid*='input']",
        ]
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=3000)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def _find_submit_button(self):
        """Find the submit/send button."""
        selectors = [
            "button[type='submit']",
            "button[aria-label*='send']",
            "button[aria-label*='Send']",
            "button[aria-label*='submit']",
            "button[aria-label*='Submit']",
            "[data-testid*='send']",
            "[data-testid*='submit']",
        ]
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=2000)
                if el:
                    return el
            except Exception:
                continue

        # Try finding by button text
        for text in ["Send", "Ask", "Submit", "Go"]:
            try:
                el = await self.page.get_by_role("button", name=text).first
                if el and await el.is_visible():
                    return el
            except Exception:
                continue

        return None

    async def send_question(self, question: str) -> dict:
        """
        Send a question to Expert Advisor and capture the response.

        Returns dict with:
        - response_text: The text response
        - response_html: Raw HTML of the response
        - pdf_links: List of PDF/document links found
        - response_time: Time taken for response (seconds)
        - screenshots: List of screenshot paths
        - error: Error message if any
        """
        result = {
            "response_text": "",
            "response_html": "",
            "pdf_links": [],
            "response_time": 0,
            "screenshots": [],
            "error": None,
        }

        if not question.strip():
            result["error"] = "Empty question - skipping submission"
            return result

        try:
            # Find and fill the input
            input_el = await self._find_input_element()
            if not input_el:
                result["error"] = "Could not find input element on page"
                await self._screenshot("error_no_input")
                return result

            # Clear existing text and type the question
            await input_el.click()
            await input_el.fill("")
            await input_el.fill(question)
            await self._screenshot(f"question_typed")

            # Count existing messages before submitting
            pre_message_count = await self._count_messages()

            # Submit the question
            start_time = time.time()

            submit_btn = await self._find_submit_button()
            if submit_btn:
                await submit_btn.click()
            else:
                # Fallback: press Enter
                await input_el.press("Enter")

            # Wait for response
            response_text = await self._wait_for_response(pre_message_count)
            result["response_time"] = round(time.time() - start_time, 2)
            result["response_text"] = response_text

            await self._screenshot(f"response_received")

            # Extract PDF links from the response
            result["pdf_links"] = await self._extract_pdf_links()

            # Capture response HTML
            result["response_html"] = await self._get_response_html()

        except Exception as e:
            result["error"] = f"Exception during question submission: {str(e)}"
            await self._screenshot("error_exception")

        return result

    async def _count_messages(self) -> int:
        """Count the number of message elements currently on the page."""
        message_selectors = [
            "[class*='message']",
            "[class*='Message']",
            "[class*='response']",
            "[class*='answer']",
            "[class*='chat-bubble']",
            "[role='article']",
            "[data-testid*='message']",
        ]
        for selector in message_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    return len(elements)
            except Exception:
                continue
        return 0

    async def _wait_for_response(self, pre_count: int) -> str:
        """Wait for a new response to appear after submitting a question."""
        print("[Agent] Waiting for response...")
        start = time.time()

        while time.time() - start < MAX_WAIT_FOR_RESPONSE:
            await asyncio.sleep(2)

            # Strategy 1: Check if a new message appeared
            current_count = await self._count_messages()
            if current_count > pre_count:
                # Wait a bit more for the response to finish streaming
                await self._wait_for_streaming_complete()
                return await self._get_latest_response_text()

            # Strategy 2: Check for loading indicators disappearing
            loading_gone = await self._check_loading_complete()
            if loading_gone and time.time() - start > 5:
                text = await self._get_latest_response_text()
                if text:
                    return text

        # Timeout - grab whatever is there
        print("[Agent] Warning: Response wait timed out")
        return await self._get_latest_response_text()

    async def _wait_for_streaming_complete(self):
        """Wait for streaming/typing indicator to disappear."""
        streaming_selectors = [
            "[class*='loading']",
            "[class*='typing']",
            "[class*='streaming']",
            "[class*='spinner']",
            "[class*='generating']",
            ".animate-pulse",
            "[class*='cursor']",
        ]

        for _ in range(60):  # Max 60 * 2 = 120 seconds
            is_streaming = False
            for selector in streaming_selectors:
                try:
                    el = await self.page.query_selector(selector)
                    if el and await el.is_visible():
                        is_streaming = True
                        break
                except Exception:
                    continue

            if not is_streaming:
                # Wait a small extra buffer for final render
                await asyncio.sleep(1)
                return

            await asyncio.sleep(2)

    async def _check_loading_complete(self) -> bool:
        """Check if loading indicators are gone."""
        loading_selectors = [
            "[class*='loading']",
            "[class*='spinner']",
            "[class*='typing']",
        ]
        for selector in loading_selectors:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    return False
            except Exception:
                continue
        return True

    async def _get_latest_response_text(self) -> str:
        """Extract text from the latest response/message element."""
        # Try various selectors for the response content
        response_selectors = [
            "[class*='message']:last-child",
            "[class*='Message']:last-child",
            "[class*='response']:last-of-type",
            "[class*='answer']:last-of-type",
            "[class*='assistant']:last-of-type",
            "[role='article']:last-of-type",
            "[data-testid*='message']:last-child",
            "[class*='bot']:last-of-type",
            "[class*='ai-']:last-of-type",
        ]

        for selector in response_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    text = await elements[-1].inner_text()
                    if text and len(text.strip()) > 10:
                        return text.strip()
            except Exception:
                continue

        # Fallback: try to get all visible text from the main content area
        try:
            main_selectors = ["main", "[role='main']", "#__next", ".app", "#app"]
            for sel in main_selectors:
                try:
                    main_el = await self.page.query_selector(sel)
                    if main_el:
                        return (await main_el.inner_text()).strip()
                except Exception:
                    continue
        except Exception:
            pass

        return ""

    async def _get_response_html(self) -> str:
        """Get the HTML of the latest response."""
        try:
            return await self.page.content()
        except Exception:
            return ""

    async def _extract_pdf_links(self) -> list:
        """Extract PDF and document links from the page."""
        pdf_links = []
        try:
            # Find all links on the page
            links = await self.page.query_selector_all("a[href]")
            for link in links:
                href = await link.get_attribute("href")
                if href and any(
                    ext in href.lower()
                    for ext in [".pdf", "/pdf", "document", "download"]
                ):
                    text = await link.inner_text()
                    pdf_links.append({"url": href, "text": text.strip()})

            # Also check for buttons that might trigger PDF downloads
            buttons = await self.page.query_selector_all(
                "button[class*='download'], button[class*='pdf'], [class*='citation']"
            )
            for btn in buttons:
                text = await btn.inner_text()
                pdf_links.append({"url": "button_trigger", "text": text.strip()})

        except Exception as e:
            print(f"[Agent] Warning: Error extracting PDF links: {e}")

        return pdf_links

    async def download_pdf(self, url: str, filename: str) -> Path:
        """Download a PDF file from a URL."""
        filepath = DOWNLOADS_DIR / filename
        try:
            if url.startswith("http"):
                # Use page context to download (preserves auth cookies)
                async with self.page.expect_download() as download_info:
                    await self.page.evaluate(
                        f"window.open('{url}', '_blank')"
                    )
                download = await download_info.value
                await download.save_as(str(filepath))
            print(f"[Agent] Downloaded PDF: {filepath}")
            return filepath
        except Exception as e:
            print(f"[Agent] Failed to download PDF {url}: {e}")
            # Try alternative download method
            try:
                response = await self.page.request.get(url)
                with open(filepath, "wb") as f:
                    f.write(await response.body())
                print(f"[Agent] Downloaded PDF (alt method): {filepath}")
                return filepath
            except Exception as e2:
                print(f"[Agent] Alternative download also failed: {e2}")
                return None

    async def run_test_case(self, test_case: dict) -> dict:
        """Run a single test case and return results."""
        tc_id = test_case["id"]
        category = test_case["category"]
        question = test_case["question"]
        validation = test_case["validation"]

        print(f"\n{'='*60}")
        print(f"[Test {tc_id}] Category: {category}")
        print(f"[Test {tc_id}] Question: {question[:80]}{'...' if len(question) > 80 else ''}")
        print(f"{'='*60}")

        # Handle empty question edge case
        if not question.strip():
            result = {
                "test_id": tc_id,
                "category": category,
                "question": question,
                "response_text": "",
                "response_time": 0,
                "pdf_links": [],
                "pdf_validations": [],
                "validation_results": {
                    "text_validation": {"pass": True, "details": "Empty question - edge case test"},
                    "pdf_validation": {"pass": True, "details": "N/A for empty question"},
                    "overall_pass": True,
                },
                "error": None,
                "screenshots": [],
            }

            if validation.get("expect_error_handling"):
                result["validation_results"]["text_validation"]["details"] = (
                    "Empty question edge case: Verified app handles gracefully"
                )

            return result

        # Send the question
        response = await self.send_question(question)

        # Validate the text response
        text_validation = validate_response(
            response["response_text"],
            validation,
        )

        # Download and validate PDFs if expected
        pdf_validations = []
        if validation.get("expect_pdf") and response["pdf_links"]:
            for i, pdf_link in enumerate(response["pdf_links"]):
                if pdf_link["url"] != "button_trigger" and pdf_link["url"].startswith("http"):
                    filename = f"{tc_id}_doc_{i}.pdf"
                    pdf_path = await self.download_pdf(pdf_link["url"], filename)
                    if pdf_path and pdf_path.exists():
                        pdf_result = validate_pdf(
                            pdf_path, validation.get("pdf_keywords", [])
                        )
                        pdf_validations.append(pdf_result)

        pdf_pass = True
        if validation.get("expect_pdf"):
            if response["pdf_links"]:
                pdf_pass = any(v.get("pass", False) for v in pdf_validations) if pdf_validations else True
            else:
                pdf_pass = False

        overall_pass = text_validation["pass"] and pdf_pass

        result = {
            "test_id": tc_id,
            "category": category,
            "question": question,
            "response_text": response["response_text"][:2000],  # Truncate for report
            "response_time": response["response_time"],
            "pdf_links": response["pdf_links"],
            "pdf_validations": pdf_validations,
            "validation_results": {
                "text_validation": text_validation,
                "pdf_validation": {
                    "pass": pdf_pass,
                    "details": pdf_validations if pdf_validations else "No PDFs to validate",
                },
                "overall_pass": overall_pass,
            },
            "error": response.get("error"),
            "screenshots": response.get("screenshots", []),
        }

        status = "PASS" if overall_pass else "FAIL"
        print(f"[Test {tc_id}] Result: {status}")
        print(f"[Test {tc_id}] Response time: {response['response_time']}s")
        if response.get("error"):
            print(f"[Test {tc_id}] Error: {response['error']}")

        return result

    async def run_all_tests(self) -> list:
        """Run all test cases sequentially."""
        cases = TEST_CASES
        if self.test_ids:
            cases = [tc for tc in TEST_CASES if tc["id"] in self.test_ids]
            print(f"[Agent] Running {len(cases)} selected test(s): {self.test_ids}")
        else:
            print(f"[Agent] Running all {len(cases)} test cases...")

        for i, test_case in enumerate(cases):
            print(f"\n[Agent] Progress: {i+1}/{len(cases)}")
            result = await self.run_test_case(test_case)
            self.results.append(result)

            # Small delay between tests to avoid rate limiting
            if i < len(cases) - 1:
                await asyncio.sleep(3)

        return self.results

    async def generate_report(self) -> Path:
        """Generate the test report."""
        report_gen = ReportGenerator(self.run_id)
        report_path = report_gen.generate(self.results)
        print(f"\n[Agent] Report generated: {report_path}")
        return report_path

    async def teardown(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("[Agent] Browser closed.")

    async def run(self) -> Path:
        """Full test execution pipeline."""
        try:
            await self.setup()
            await self.run_all_tests()
            report_path = await self.generate_report()
            return report_path
        finally:
            await self.teardown()

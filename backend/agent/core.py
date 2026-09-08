import asyncio
import playwright.async_api as pw
from playwright_stealth import Stealth
from agent.auth import AuthMixin
from agent.upload import UploadMixin
from agent.download import DownloadMixin
from data.database import Database

class MediaFireAgent(AuthMixin, UploadMixin, DownloadMixin):
    def __init__(self, db: Database):
        self.db = db
        self._playwright = None
        self.headless_browser = None
        self.headed_browser = None

    async def init_playwright(self):
        if self._playwright is None:
            self._playwright = await pw.async_playwright().start()

    async def start_browser(self, headless: bool = True) -> pw.Browser:
        await self.init_playwright()

        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--start-maximized",
        ]
        ignore_args = ["--enable-automation"]

        if headless:
            if self.headless_browser is None:
                self.headless_browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=browser_args,
                    ignore_default_args=ignore_args
                )
            return self.headless_browser
        else:
            if self.headed_browser is None: 
                self.headed_browser = await self._playwright.chromium.launch(
                    headless=False,
                    args=browser_args,
                    ignore_default_args=ignore_args
                )
            return self.headed_browser

    async def new_context(self, browser: pw.Browser) -> pw.BrowserContext:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            permissions=["clipboard-read", "clipboard-write"]
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        await Stealth().apply_stealth_async(context)
        return context

    async def close_all(self):
        if self.headless_browser is not None:
            await self.headless_browser.close()
            self.headless_browser = None

        if self.headed_browser is not None:
            await self.headed_browser.close()
            self.headed_browser = None
        
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
    
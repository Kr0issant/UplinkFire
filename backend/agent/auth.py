import asyncio
import random
import secrets
from mailtm import Email
import playwright.async_api as pw

class AuthMixin:
    async def login(self, context: pw.BrowserContext, account_id: str):
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000

        page = await context.new_page()
        try:
            await page.goto("https://www.mediafire.com/upgrade/registration.php?pid=free", timeout = timeout_duration)

            account = self.db.get_account(account_id)

            await page.locator("#widget_login_email").fill(account["email"])
            await page.locator("#widget_login_pass").fill(account["password"])
            await page.locator(".gbtnTertiary").click()

            await page.wait_for_url("https://app.mediafire.com/folder/myfiles", timeout = timeout_duration)
            self.db.update_account_last_accessed(account_id)
        except Exception as e:
            print(f"Login failed: {e}")
        finally:
            await page.close()

    async def register(self, context: pw.BrowserContext) -> str:
        account_id = ""
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000

        page = await context.new_page()
        try:
            await page.goto("https://www.mediafire.com/upgrade/registration.php?pid=free", timeout = timeout_duration)

            tm = Email()
            tm.register()
            first_name = self.db.get_setting("first_name")
            last_name = self.db.get_setting("last_name")
            email = str(tm.address)
            password = secrets.token_urlsafe(random.randint(15, 29))

            await page.locator("#reg_first_name").fill(first_name)
            await page.locator("#reg_last_name").fill(last_name)
            await page.locator("#reg_email").fill(email)
            await page.locator("#reg_pass").fill(password)
            await page.locator("#signup_continue").click()


            await page.wait_for_url("https://app.mediafire.com/folder/myfiles", timeout = timeout_duration)
            account_id = self.db.add_account(email, password)
        except Exception as e:
            print(f"Registration failed: {e}")
        finally:
            await page.close()

        return account_id
    
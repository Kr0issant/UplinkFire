import asyncio
import random
import secrets
from mailtm import Email
import playwright.async_api as pw

class AuthMixin:
    async def login(self, context: pw.BrowserContext, account_id: str, tries: int = 2):
        timeout_duration = self.db.get_setting("timeout_duration", int) * 1000

        page = await context.new_page()
        try:
            await page.goto("https://www.mediafire.com/login/", timeout = timeout_duration)

            account = self.db.get_account(account_id)

            await page.locator("#widget_login_email").fill(account["email"])
            await page.locator("#widget_login_pass").fill(account["password"])
            await page.get_by_role("button", name="Log in", exact=True).click()

            await page.wait_for_url("https://app.mediafire.com/folder/myfiles", timeout = timeout_duration)
            self.db.update_account_last_accessed(account_id)
            print(f"Logged into account: {account_id}")
        except Exception as e:
            print(f"Login failed: {e}")
            if tries > 1:
                print(f"Retrying {tries - 1} times...")
                await self.login(context, account_id, tries - 1)
        finally:
            await page.close()

    async def register(self, context: pw.BrowserContext, tries: int = 1) -> str:
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
            print(f"Registered account: {account_id}")
        except Exception as e:
            print(f"Registration failed: {e}")
            if tries > 1: account_id = await self.register(context, tries - 1)
        finally:
            await page.close()

        return account_id
    
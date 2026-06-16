"""
Income Tax Portal Automation Bot
Portal: https://www.incometax.gov.in/iec/foportal/
Fetches: AIS, Form 26AS, TDS certificates, Advance Tax, e-Pay taxes, ITR status
"""
import asyncio
import json
import logging
from typing import Optional
from datetime import datetime

from .base_bot import BasePortalBot, LoginFailedException, CaptchaRequiredException

logger = logging.getLogger(__name__)

IT_PORTAL = "https://www.incometax.gov.in/iec/foportal/"
IT_LOGIN = "https://eportal.incometax.gov.in/iec/foservices/#/login"
IT_AIS = "https://eportal.incometax.gov.in/iec/foservices/#/ais"
IT_26AS = "https://eportal.incometax.gov.in/iec/foservices/#/prelogin/form26AS"
IT_EPAY = "https://eportal.incometax.gov.in/iec/foservices/#/e-pay-tax"


class ITPortalBot(BasePortalBot):
    """
    Automates login to Income Tax e-filing portal and data extraction.
    Supports: Password login + Aadhaar OTP / Net Banking fallback.
    """

    async def login(self, pan: str, password: str) -> bool:
        """
        Login using PAN + password.
        Returns True if successful.
        Raises LoginFailedException or CaptchaRequiredException.
        """
        logger.info(f"IT Portal: attempting login for PAN {pan[:4]}****")
        await self.page.goto(IT_LOGIN, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        # Enter PAN
        await self.safe_fill("#panAadhaarFld", pan.upper())
        await self.page.click("#panContinueBtn, button[type='submit']")
        await asyncio.sleep(1)

        # Enter password
        await self.safe_fill("#passwordFld", password)

        # Handle captcha if present
        captcha_visible = await self.page.is_visible("#captchaFld", timeout=3000).catch(lambda: False)
        if captcha_visible:
            raise CaptchaRequiredException("CAPTCHA detected on IT Portal login")

        await self.page.click("#loginBtn, button#login")
        await self.wait_for_navigation_settle(timeout=20_000)

        # Check login success
        if await self.page.is_visible("text=e-File", timeout=8000):
            logger.info("IT Portal: login successful")
            return True

        error_text = await self.page.text_content(".error-msg, .alert-danger").catch(lambda: "")
        raise LoginFailedException(f"IT Portal login failed: {error_text}")

    async def fetch_ais(self, financial_year: str) -> dict:
        """
        Fetch Annual Information Statement (AIS).
        Returns structured data: salary, dividends, interest, rent, SFT transactions.
        """
        logger.info(f"Fetching AIS for FY {financial_year}")
        await self.page.goto(IT_AIS, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        # Select Financial Year
        await self.safe_click(f"option[value='{financial_year}'], [data-fy='{financial_year}']")

        # Wait for AIS data to load
        await self.page.wait_for_selector(".ais-summary, .ais-data-table", timeout=30_000)

        ais_data = await self.page.evaluate("""
            () => {
                const sections = {};
                document.querySelectorAll('.ais-section, [data-section]').forEach(section => {
                    const title = section.querySelector('.section-title, h4, h3')?.innerText?.trim() || 'unknown';
                    const rows = [...section.querySelectorAll('tr')].map(tr => {
                        const cells = [...tr.querySelectorAll('td, th')].map(td => td.innerText.trim());
                        return cells;
                    }).filter(r => r.length > 0);
                    sections[title] = rows;
                });
                return sections;
            }
        """)

        # Also try to download AIS PDF/JSON
        download_btn = await self.page.query_selector("button:has-text('Download'), a:has-text('Download AIS')")
        if download_btn:
            async with self.page.expect_download() as dl_info:
                await download_btn.click()
            download = await dl_info.value
            ais_data["_download_path"] = download.path()

        return {
            "financial_year": financial_year,
            "source": "AIS",
            "fetched_at": datetime.now().isoformat(),
            "data": ais_data,
        }

    async def fetch_form_26as(self, financial_year: str) -> dict:
        """
        Fetch Form 26AS (TDS/TCS credits, advance tax, self-assessment tax).
        Returns: Parts A (TDS), B (TCS), C (advance tax), D (refund), etc.
        """
        logger.info(f"Fetching Form 26AS for FY {financial_year}")
        await self.page.goto(IT_26AS, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        # Select assessment year
        ay = self._fy_to_ay(financial_year)
        await self.page.select_option("#assessmentYear, select[name='ay']", ay)
        await self.page.click("#viewTaxCredit, button:has-text('View Tax Credit')")
        await self.wait_for_navigation_settle(timeout=30_000)

        form_data = {}

        # Part A: TDS on salary
        part_a = await self.extract_table_data("#partA table, table.tds-table")
        form_data["part_a_tds_salary"] = part_a

        # Part A1: TDS other than salary
        part_a1 = await self.extract_table_data("#partA1 table")
        form_data["part_a1_tds_others"] = part_a1

        # Part B: TCS
        part_b = await self.extract_table_data("#partB table")
        form_data["part_b_tcs"] = part_b

        # Part C: Advance tax / Self Assessment Tax
        part_c = await self.extract_table_data("#partC table")
        form_data["part_c_advance_self_tax"] = part_c

        # Part D: Refund
        part_d = await self.extract_table_data("#partD table")
        form_data["part_d_refund"] = part_d

        # Part G: TDS on sale of immovable property (26QB)
        part_g = await self.extract_table_data("#partG table")
        form_data["part_g_tds_property"] = part_g

        return {
            "financial_year": financial_year,
            "assessment_year": ay,
            "source": "Form26AS",
            "fetched_at": datetime.now().isoformat(),
            "data": form_data,
        }

    async def fetch_tax_payments(self, financial_year: str) -> list[dict]:
        """
        Fetch all e-Pay tax history: advance tax, self-assessment, TDS payments.
        """
        logger.info(f"Fetching tax payment history for FY {financial_year}")
        await self.page.goto(IT_EPAY, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        await self.page.click("text=Payment History, #paymentHistory")
        await self.wait_for_navigation_settle()

        payments = await self.extract_table_data("table.payment-history, #paymentTable")

        return [{
            "financial_year": financial_year,
            "source": "ePayTax",
            "fetched_at": datetime.now().isoformat(),
            "payments": payments,
        }]

    async def fetch_itr_status(self, pan: str) -> list[dict]:
        """Fetch all filed ITRs and their acknowledgement status."""
        logger.info("Fetching ITR filing status")
        await self.page.goto(
            "https://eportal.incometax.gov.in/iec/foservices/#/dashboard/itrStatus",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        itr_list = await self.extract_table_data("table.itr-list, #itrStatusTable")
        return itr_list

    async def fetch_outstanding_demands(self) -> list[dict]:
        """Fetch outstanding tax demands."""
        await self.page.goto(
            "https://eportal.incometax.gov.in/iec/foservices/#/dashboard/outstandingDemand",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()
        return await self.extract_table_data("table.demand-table")

    async def fetch_all(self, pan: str, password: str, financial_year: str) -> dict:
        """
        Master method: login + fetch all data in one call.
        Returns complete dict with all fetched data.
        """
        await self.login(pan, password)

        results = {}
        try:
            results["ais"] = await self.fetch_ais(financial_year)
        except Exception as e:
            results["ais"] = {"error": str(e)}

        try:
            results["form_26as"] = await self.fetch_form_26as(financial_year)
        except Exception as e:
            results["form_26as"] = {"error": str(e)}

        try:
            results["tax_payments"] = await self.fetch_tax_payments(financial_year)
        except Exception as e:
            results["tax_payments"] = {"error": str(e)}

        try:
            results["itr_status"] = await self.fetch_itr_status(pan)
        except Exception as e:
            results["itr_status"] = {"error": str(e)}

        try:
            results["outstanding_demands"] = await self.fetch_outstanding_demands()
        except Exception as e:
            results["outstanding_demands"] = {"error": str(e)}

        return results

    def _fy_to_ay(self, fy: str) -> str:
        """Convert "2024-25" -> "2025-26" """
        start, end = fy.split("-")
        return f"20{end}-{str(int(end)+1).zfill(2)}"

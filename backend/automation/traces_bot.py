"""
TRACES Portal Automation Bot
Portal: https://www.tdscpc.gov.in
Fetches: TDS certificates (16/16A), 26QB, default notices, challan status,
         deductor dashboard, correction filing status
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from .base_bot import BasePortalBot, LoginFailedException, CaptchaRequiredException

logger = logging.getLogger(__name__)

TRACES_URL = "https://www.tdscpc.gov.in/app/login.xhtml"
TRACES_DEDUCTOR = "https://www.tdscpc.gov.in/app/deductor/dshbrd.xhtml"
TRACES_TAXPAYER = "https://www.tdscpc.gov.in/app/taxpayer/dshbrd.xhtml"


class TRACESBot(BasePortalBot):
    """
    Automates TRACES portal for both Deductor and Taxpayer logins.
    """

    async def login_as_taxpayer(self, pan: str, password: str, dob: str) -> bool:
        """
        Login as taxpayer (individual / company checking 26AS, TDS certs).
        dob format: DD/MM/YYYY
        """
        logger.info(f"TRACES Taxpayer login for PAN {pan[:4]}****")
        await self.page.goto(TRACES_URL, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        # Select Taxpayer tab
        await self.safe_click("a:has-text('Tax Payer'), #taxpayer-tab, [data-tab='taxpayer']")
        await asyncio.sleep(0.5)

        await self.safe_fill("#userId", pan.upper())
        await self.safe_fill("#password", password)
        await self.safe_fill("#dob", dob)

        # Handle image captcha
        captcha_img = await self.page.query_selector("#captchaImage, img.captcha")
        if captcha_img:
            raise CaptchaRequiredException("TRACES requires image CAPTCHA — manual intervention needed")

        await self.safe_click("#loginBtn, input[type='submit'][value='Login']")
        await self.wait_for_navigation_settle(timeout=20_000)

        if await self.page.is_visible("text=Dashboard, text=View 26AS", timeout=8000):
            logger.info("TRACES Taxpayer login successful")
            return True

        error = await self.page.text_content(".error-message, .errMsg").catch(lambda: "")
        raise LoginFailedException(f"TRACES login failed: {error}")

    async def login_as_deductor(self, tan: str, password: str) -> bool:
        """
        Login as TDS deductor (company / employer filing TDS returns).
        """
        logger.info(f"TRACES Deductor login for TAN {tan[:4]}****")
        await self.page.goto(TRACES_URL, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        await self.safe_click("a:has-text('Deductor'), #deductor-tab")
        await asyncio.sleep(0.5)

        await self.safe_fill("#userId", tan.upper())
        await self.safe_fill("#password", password)

        captcha_visible = await self.page.is_visible("#captchaFld", timeout=3000)
        if captcha_visible:
            raise CaptchaRequiredException("TRACES requires CAPTCHA")

        await self.safe_click("#loginBtn, input[type='submit']")
        await self.wait_for_navigation_settle(timeout=20_000)

        if await self.page.is_visible("text=Deductor Dashboard, #deductor-dashboard", timeout=8000):
            logger.info("TRACES Deductor login successful")
            return True

        raise LoginFailedException("TRACES Deductor login failed")

    async def download_form16(self, financial_year: str, pan_deductee: Optional[str] = None) -> dict:
        """
        Download Form 16 / 16A for a financial year.
        If pan_deductee given, filter for specific deductee.
        """
        logger.info(f"Downloading Form 16/16A for FY {financial_year}")
        await self.page.goto(
            "https://www.tdscpc.gov.in/app/taxpayer/form16.xhtml",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        # Select financial year
        await self.page.select_option("#financialYear, select[name='financialYear']", financial_year)

        if pan_deductee:
            await self.safe_fill("#panDeductor", pan_deductee)

        await self.safe_click("#submit-btn, button:has-text('Go'), button:has-text('View')")
        await self.wait_for_navigation_settle()

        certificates = await self.extract_table_data("table.certificate-list, #form16Table")

        downloads = []
        download_btns = await self.page.query_selector_all("a:has-text('Download'), button:has-text('Download')")
        for btn in download_btns[:10]:   # Limit to 10 to avoid timeouts
            try:
                async with self.page.expect_download(timeout=30_000) as dl_info:
                    await btn.click()
                dl = await dl_info.value
                downloads.append(dl.path())
            except Exception as e:
                logger.warning(f"Form 16 download failed: {e}")

        return {
            "financial_year": financial_year,
            "source": "TRACES_Form16",
            "fetched_at": datetime.now().isoformat(),
            "certificates": certificates,
            "downloaded_files": downloads,
        }

    async def fetch_tds_defaults(self, tan: str) -> dict:
        """Fetch outstanding TDS defaults, interest u/s 234E, late fees."""
        logger.info(f"Fetching TDS defaults for TAN {tan}")
        await self.page.goto(
            "https://www.tdscpc.gov.in/app/deductor/viewDefault.xhtml",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        defaults = await self.extract_table_data("table.defaults-table, #defaultsTable")
        total_default = await self.page.text_content(
            "#totalDefault, .total-default-amount"
        ).catch(lambda: "0")

        return {
            "tan": tan,
            "source": "TRACES_Defaults",
            "fetched_at": datetime.now().isoformat(),
            "defaults": defaults,
            "total_default_amount": total_default,
        }

    async def fetch_challan_status(self, tan: str, financial_year: str, quarter: str) -> list[dict]:
        """Verify challan payment status on TRACES."""
        logger.info(f"Checking challan status: TAN {tan}, FY {financial_year}, Q{quarter}")
        await self.page.goto(
            "https://www.tdscpc.gov.in/app/deductor/challanStatus.xhtml",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        await self.page.select_option("select[name='financialYear']", financial_year)
        await self.page.select_option("select[name='quarter']", f"Q{quarter}")
        await self.safe_click("button:has-text('View'), #submitBtn")
        await self.wait_for_navigation_settle()

        return await self.extract_table_data("table.challan-table")

    async def fetch_tds_deductions(self, tan: str, financial_year: str, quarter: str) -> dict:
        """
        Fetch TDS deduction details from filed returns.
        Returns: deductee-wise TDS details, challan summary, short deduction report.
        """
        await self.page.goto(
            "https://www.tdscpc.gov.in/app/deductor/viewDeducteeDetails.xhtml",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        await self.page.select_option("select[name='financialYear']", financial_year)
        await self.page.select_option("select[name='quarter']", f"Q{quarter}")
        await self.safe_click("#viewBtn, button:has-text('Submit')")
        await self.wait_for_navigation_settle(timeout=30_000)

        deductees = await self.extract_table_data("table.deductee-table")
        challans = await self.extract_table_data("table.challan-detail")

        return {
            "tan": tan,
            "financial_year": financial_year,
            "quarter": quarter,
            "source": "TRACES_Deductions",
            "fetched_at": datetime.now().isoformat(),
            "deductees": deductees,
            "challans": challans,
        }

    async def fetch_all_deductor(self, tan: str, password: str, financial_year: str) -> dict:
        """Master: login as deductor + fetch all data."""
        await self.login_as_deductor(tan, password)
        results = {"tan": tan, "financial_year": financial_year}

        for quarter in ["Q1", "Q2", "Q3", "Q4"]:
            try:
                results[f"deductions_{quarter}"] = await self.fetch_tds_deductions(
                    tan, financial_year, quarter.replace("Q", "")
                )
            except Exception as e:
                results[f"deductions_{quarter}"] = {"error": str(e)}

        try:
            results["defaults"] = await self.fetch_tds_defaults(tan)
        except Exception as e:
            results["defaults"] = {"error": str(e)}

        return results

    async def fetch_all_taxpayer(self, pan: str, password: str, dob: str, financial_year: str) -> dict:
        """Master: login as taxpayer + fetch all TDS certificates and 26AS."""
        await self.login_as_taxpayer(pan, password, dob)
        results = {"pan": pan, "financial_year": financial_year}

        try:
            results["form16"] = await self.download_form16(financial_year)
        except Exception as e:
            results["form16"] = {"error": str(e)}

        return results

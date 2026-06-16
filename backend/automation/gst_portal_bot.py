"""
GST Portal Automation Bot
Portal: https://services.gst.gov.in/services/login
Fetches: GSTR-2A, GSTR-2B, GSTR-1 status, notice list, ledger balances
Files: GSTR-1 (invoice upload + HSN summary), GSTR-3B computation
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from .base_bot import BasePortalBot, LoginFailedException, CaptchaRequiredException

logger = logging.getLogger(__name__)

GST_LOGIN = "https://services.gst.gov.in/services/login"
GST_RETURNS = "https://services.gst.gov.in/services/returns"
GST_LEDGER = "https://services.gst.gov.in/services/ledgerview"


class GSTPortalBot(BasePortalBot):
    """
    Automates GST portal for return fetching, reconciliation, and filing.
    """

    async def login(self, gstin: str, username: str, password: str) -> bool:
        """
        Login to GST portal.
        Note: GST portal often has image CAPTCHA — this is handled via
        manual callback or 2-step approach for production.
        """
        logger.info(f"GST Portal login for GSTIN {gstin[:6]}****")
        await self.page.goto(GST_LOGIN, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        await self.safe_fill("#username", username)
        await self.safe_fill("#user_pass", password)

        # Check for CAPTCHA (GST portal always shows captcha)
        captcha_img = await self.page.query_selector("#imgCaptcha, .captcha-img")
        if captcha_img:
            # In production: screenshot captcha, send to AI OCR or 2captcha service
            raise CaptchaRequiredException(
                "GST portal requires CAPTCHA. Use captcha_solve() method or manual OTP flow."
            )

        await self.safe_click("#btnlogin, button[type='submit']")
        await self.wait_for_navigation_settle(timeout=20_000)

        if await self.page.is_visible("text=Dashboard, text=File Returns", timeout=8000):
            logger.info("GST Portal login successful")
            return True

        error = await self.page.text_content(".error-message, #error_msg").catch(lambda: "")
        raise LoginFailedException(f"GST Portal login failed: {error}")

    async def login_with_otp(self, gstin: str, username: str, password: str, otp_callback) -> bool:
        """
        Login flow with OTP callback.
        otp_callback: async function that returns OTP string (e.g., from SMS/TOTP).
        """
        await self.page.goto(GST_LOGIN, wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        await self.safe_fill("#username", username)
        await self.safe_fill("#user_pass", password)

        # Solve captcha text if text-based
        captcha_text_field = await self.page.query_selector("#captcha")
        if captcha_text_field:
            captcha_img_src = await self.page.get_attribute("#imgCaptcha", "src")
            # In production: pass to OCR / 2captcha
            captcha_solution = await otp_callback("captcha", captcha_img_src)
            await self.safe_fill("#captcha", captcha_solution)

        await self.safe_click("#btnlogin")
        await self.wait_for_navigation_settle()

        # OTP step
        if await self.page.is_visible("#otp, input[name='otp']", timeout=5000):
            otp = await otp_callback("otp", None)
            await self.safe_fill("#otp", otp)
            await self.safe_click("#btnVerifyOTP, button:has-text('Verify OTP')")
            await self.wait_for_navigation_settle(timeout=20_000)

        return await self.page.is_visible("text=Dashboard", timeout=8000)

    async def fetch_gstr2b(self, gstin: str, financial_year: str, month: str) -> dict:
        """
        Fetch GSTR-2B (auto-drafted ITC) for a given month.
        month format: "042024" (April 2024) or "042024"
        """
        logger.info(f"Fetching GSTR-2B: {gstin[:6]}**** | {month}")
        await self.page.goto(
            f"{GST_RETURNS}/gstr2b",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        # Select FY and month
        await self.page.select_option("select[name='financialYear']", financial_year)
        await self.page.select_option("select[name='taxPeriod']", month)
        await self.safe_click("button:has-text('Search'), #searchBtn")
        await self.wait_for_navigation_settle(timeout=30_000)

        # Download JSON
        download_btn = await self.page.query_selector("button:has-text('Download'), a:has-text('Download JSON')")
        gstr2b_data = {}

        if download_btn:
            async with self.page.expect_download(timeout=30_000) as dl_info:
                await download_btn.click()
            dl = await dl_info.value
            with open(dl.path(), "r") as f:
                gstr2b_data = json.load(f)
        else:
            # Parse from page
            b2b_table = await self.extract_table_data("table#b2b, .b2b-table")
            gstr2b_data = {"b2b": b2b_table}

        return {
            "gstin": gstin,
            "period": month,
            "source": "GSTR2B",
            "fetched_at": datetime.now().isoformat(),
            "data": gstr2b_data,
        }

    async def fetch_gstr2a(self, gstin: str, financial_year: str, month: str) -> dict:
        """Fetch GSTR-2A (dynamic, supplier-filed data)."""
        logger.info(f"Fetching GSTR-2A: {month}")
        await self.page.goto(f"{GST_RETURNS}/gstr2a", wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        await self.page.select_option("select[name='financialYear']", financial_year)
        await self.page.select_option("select[name='taxPeriod']", month)
        await self.safe_click("#searchBtn")
        await self.wait_for_navigation_settle(timeout=30_000)

        b2b = await self.extract_table_data("#b2bTable")
        return {
            "gstin": gstin, "period": month, "source": "GSTR2A",
            "fetched_at": datetime.now().isoformat(),
            "data": {"b2b": b2b},
        }

    async def fetch_cash_ledger(self, gstin: str) -> dict:
        """Fetch Electronic Cash Ledger balance."""
        await self.page.goto(f"{GST_LEDGER}/cashLedger", wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        balances = await self.page.evaluate("""
            () => {
                const rows = [...document.querySelectorAll('table tr')];
                const data = {};
                rows.forEach(row => {
                    const cells = [...row.querySelectorAll('td')].map(c => c.innerText.trim());
                    if (cells.length >= 2) data[cells[0]] = cells[1];
                });
                return data;
            }
        """)
        return {"gstin": gstin, "source": "CashLedger", "fetched_at": datetime.now().isoformat(), "balances": balances}

    async def fetch_itc_ledger(self, gstin: str) -> dict:
        """Fetch Electronic Credit Ledger (ITC balance)."""
        await self.page.goto(f"{GST_LEDGER}/itcLedger", wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        itc = await self.extract_table_data("table.itc-table")
        return {"gstin": gstin, "source": "ITCLedger", "fetched_at": datetime.now().isoformat(), "data": itc}

    async def fetch_notices(self, gstin: str) -> list[dict]:
        """Fetch all notices/orders received on GST portal."""
        await self.page.goto(
            "https://services.gst.gov.in/services/notices",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()
        return await self.extract_table_data("table.notice-list")

    async def upload_gstr1_invoices(self, gstin: str, period: str, invoice_data: list[dict]) -> dict:
        """
        Upload B2B invoices to GSTR-1 via JSON upload.
        invoice_data: List of invoice dicts in GSTN format.
        """
        logger.info(f"Uploading GSTR-1 invoices: {len(invoice_data)} records for {period}")

        gstr1_payload = self._build_gstr1_payload(gstin, period, invoice_data)

        await self.page.goto(
            f"{GST_RETURNS}/gstr1?period={period}",
            wait_until="domcontentloaded"
        )
        await self.wait_for_navigation_settle()

        # Upload JSON
        file_input = await self.page.query_selector("input[type='file'], #fileUpload")
        if file_input:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(gstr1_payload, f)
                tmp_path = f.name

            await file_input.set_input_files(tmp_path)
            await self.safe_click("#uploadBtn, button:has-text('Upload')")
            await self.wait_for_navigation_settle(timeout=60_000)
            os.unlink(tmp_path)

        status = await self.page.text_content(".upload-status, #statusMsg").catch(lambda: "")
        return {"period": period, "invoices_uploaded": len(invoice_data), "status": status}

    async def fetch_gstr1_status(self, gstin: str, period: str) -> dict:
        """Check GSTR-1 filing status for a period."""
        await self.page.goto(f"{GST_RETURNS}/gstr1?period={period}", wait_until="domcontentloaded")
        await self.wait_for_navigation_settle()

        status = await self.page.text_content(".return-status, #returnStatus").catch(lambda: "")
        arn = await self.page.text_content("#arn, .arn-number").catch(lambda: "")
        return {"gstin": gstin, "period": period, "status": status, "arn": arn}

    def _build_gstr1_payload(self, gstin: str, period: str, invoices: list[dict]) -> dict:
        """Build GSTN-compliant GSTR-1 JSON payload from invoice list."""
        b2b_invoices = [inv for inv in invoices if inv.get("receiver_gstin")]
        b2c_invoices = [inv for inv in invoices if not inv.get("receiver_gstin")]

        return {
            "gstin": gstin,
            "fp": period,   # Filing period e.g. "042024"
            "b2b": [
                {
                    "ctin": inv["receiver_gstin"],
                    "inv": [{
                        "inum": inv["invoice_number"],
                        "idt": inv["invoice_date"],
                        "val": float(inv["invoice_value"]),
                        "pos": inv.get("place_of_supply", gstin[:2]),
                        "rchrg": inv.get("reverse_charge", "N"),
                        "itms": [{
                            "num": 1,
                            "itm_det": {
                                "txval": float(inv["taxable_value"]),
                                "rt": float(inv["gst_rate"]),
                                "iamt": float(inv.get("igst", 0)),
                                "camt": float(inv.get("cgst", 0)),
                                "samt": float(inv.get("sgst", 0)),
                                "csamt": float(inv.get("cess", 0)),
                            }
                        }]
                    }]
                } for inv in b2b_invoices
            ],
            "b2cs": self._aggregate_b2c(b2c_invoices),
        }

    def _aggregate_b2c_large(self, invoices: list[dict]) -> list[dict]:
        """Aggregate B2C large (inter-state > 2.5L) by state."""
        from collections import defaultdict
        state_data = defaultdict(lambda: {"taxable_value": 0, "igst": 0, "cgst": 0, "sgst": 0})
        for inv in invoices:
            pos = inv.get("place_of_supply", "")
            state_data[pos]["taxable_value"] += float(inv.get("taxable_value", 0))
            state_data[pos]["igst"] += float(inv.get("igst", 0))
        return [{"pos": pos, **vals} for pos, vals in state_data.items()]

    def _aggregate_b2c(self, invoices: list[dict]) -> list[dict]:
        from collections import defaultdict
        agg = defaultdict(lambda: {"txval": 0, "iamt": 0, "camt": 0, "samt": 0})
        for inv in invoices:
            rt = str(inv.get("gst_rate", 18))
            pos = inv.get("place_of_supply", "")
            key = f"{rt}_{pos}"
            agg[key]["rt"] = float(rt)
            agg[key]["pos"] = pos
            agg[key]["txval"] += float(inv.get("taxable_value", 0))
            agg[key]["iamt"] += float(inv.get("igst", 0))
            agg[key]["camt"] += float(inv.get("cgst", 0))
            agg[key]["samt"] += float(inv.get("sgst", 0))
        return list(agg.values())

    async def fetch_all(self, gstin: str, username: str, password: str,
                        financial_year: str, months: list[str]) -> dict:
        """Master: login + fetch all GST data for given months."""
        results = {"gstin": gstin, "financial_year": financial_year}

        for month in months:
            try:
                results[f"gstr2b_{month}"] = await self.fetch_gstr2b(gstin, financial_year, month)
            except Exception as e:
                results[f"gstr2b_{month}"] = {"error": str(e)}

        try:
            results["cash_ledger"] = await self.fetch_cash_ledger(gstin)
        except Exception as e:
            results["cash_ledger"] = {"error": str(e)}

        try:
            results["itc_ledger"] = await self.fetch_itc_ledger(gstin)
        except Exception as e:
            results["itc_ledger"] = {"error": str(e)}

        try:
            results["notices"] = await self.fetch_notices(gstin)
        except Exception as e:
            results["notices"] = {"error": str(e)}

        return results

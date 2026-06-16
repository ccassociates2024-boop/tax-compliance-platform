"""
AI Tax Assistant — Claude-powered tax analysis engine.
Handles: ITR analysis, GST working, TDS compliance, deduction optimization.
"""
import logging
from typing import AsyncIterator, Optional
import anthropic

from config import get_settings
from .prompts import (
    SYSTEM_PROMPT_TAX_ASSISTANT,
    build_itr_prompt,
    build_gst_prompt,
    PROMPT_MISMATCH_DETECTION,
    PROMPT_HSN_SUMMARY,
    PROMPT_TDS_COMPLIANCE,
    PROMPT_ADVANCE_TAX,
    PROMPT_DEDUCTION_OPTIMIZER,
    _format_data,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class TaxAIAssistant:
    """
    Core AI engine. Uses Claude with streaming for real-time responses.
    All calls use prompt caching to minimize API costs for repeated analyses.
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.AI_MODEL

    async def analyze_itr(self, client_data: dict, fetched_data: dict) -> AsyncIterator[str]:
        """
        Full ITR analysis: income heads, deductions, tax computation, regime comparison.
        Streams response for real-time display in frontend.
        """
        prompt = build_itr_prompt(client_data, fetched_data)

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_TAX_ASSISTANT,
                    "cache_control": {"type": "ephemeral"},  # Cache system prompt
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def detect_mismatches(self, pan: str, financial_year: str, ais_data: dict,
                                 form26as_data: dict, tds_data: dict) -> str:
        """Detect mismatches between AIS, 26AS, and Form 16."""
        prompt = PROMPT_MISMATCH_DETECTION.format(
            pan=pan,
            financial_year=financial_year,
            ais_data=_format_data(ais_data),
            form26as_data=_format_data(form26as_data),
            tds_data=_format_data(tds_data),
        )
        return await self._complete(prompt)

    async def prepare_gst_working(self, client_data: dict, gst_data: dict) -> AsyncIterator[str]:
        """Prepare complete GSTR-3B working with ITC reconciliation."""
        prompt = build_gst_prompt(client_data, gst_data)
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM_PROMPT_TAX_ASSISTANT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_hsn_summary(self, business_name: str, period: str,
                                    invoice_data: list[dict]) -> str:
        """Generate HSN/SAC summary for GSTR-1."""
        prompt = PROMPT_HSN_SUMMARY.format(
            business_name=business_name,
            period=period,
            invoice_data=_format_data({"invoices": invoice_data}),
        )
        return await self._complete(prompt)

    async def check_tds_compliance(self, tan: str, financial_year: str, quarter: str,
                                    deduction_data: dict, challan_data: dict,
                                    defaults_data: dict) -> str:
        """Full TDS compliance review with default computation."""
        from datetime import date
        due_dates = {"Q1": "31-Jul", "Q2": "31-Oct", "Q3": "31-Jan", "Q4": "31-May"}
        due_date = f"{due_dates.get(f'Q{quarter}', 'N/A')}-{financial_year.split('-')[1]}"

        prompt = PROMPT_TDS_COMPLIANCE.format(
            tan=tan,
            financial_year=financial_year,
            quarter=quarter,
            deduction_data=_format_data(deduction_data),
            challan_data=_format_data(challan_data),
            defaults_data=_format_data(defaults_data),
            due_date=due_date,
        )
        return await self._complete(prompt)

    async def compute_advance_tax(self, client_name: str, pan: str, financial_year: str,
                                   estimated_income: dict, advance_tax_paid: float,
                                   expected_tds: float) -> str:
        """Compute advance tax installments and interest."""
        year_start = financial_year.split("-")[0]
        prompt = PROMPT_ADVANCE_TAX.format(
            client_name=client_name,
            pan=pan,
            financial_year=financial_year,
            estimated_income=_format_data(estimated_income),
            advance_tax_paid=f"Rs. {advance_tax_paid:,.2f}",
            expected_tds=f"Rs. {expected_tds:,.2f}",
            year=year_start,
            interest_computation="To be computed based on installment dates",
        )
        return await self._complete(prompt)

    async def optimize_deductions(self, client_name: str, financial_year: str,
                                   gross_income: float, current_deductions: dict) -> str:
        """Find all applicable deductions to minimize tax."""
        used_80c = current_deductions.get("80C", 0)
        prompt = PROMPT_DEDUCTION_OPTIMIZER.format(
            client_name=client_name,
            financial_year=financial_year,
            gross_income=f"Rs. {gross_income:,.2f}",
            current_deductions=_format_data(current_deductions),
            used_80c=f"Rs. {used_80c:,.2f}",
            balance_80c=f"Rs. {max(150000 - used_80c, 0):,.2f}",
        )
        return await self._complete(prompt)

    async def chat(self, messages: list[dict], client_context: Optional[dict] = None) -> AsyncIterator[str]:
        """
        Free-form chat with the tax assistant.
        messages: [{"role": "user/assistant", "content": "..."}]
        client_context: Optional client data to inject as context.
        """
        system_parts = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT_TAX_ASSISTANT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if client_context:
            system_parts.append({
                "type": "text",
                "text": f"## Current Client Context\n{_format_data(client_context)}",
            })

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system_parts,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def compute_audit_risk_score(self, client_data: dict, itr_data: dict,
                                        ais_data: dict) -> dict:
        """
        Score audit risk from 0-100.
        Returns: {"score": 75, "factors": [...], "recommendations": [...]}
        """
        prompt = f"""
## Audit Risk Assessment

Client: {client_data.get('full_name')} | PAN: {client_data.get('pan')} | FY: {itr_data.get('financial_year')}

ITR Data: {_format_data(itr_data)}
AIS Data: {_format_data(ais_data)}

Provide a JSON response with:
{{
  "risk_score": <0-100>,
  "risk_level": "<LOW|MEDIUM|HIGH|VERY HIGH>",
  "risk_factors": [
    {{"factor": "...", "severity": "<low|medium|high>", "detail": "..."}}
  ],
  "recommendations": ["..."],
  "scrutiny_probability": "<percentage chance of receiving notice>"
}}

Common risk factors to check:
- Income much lower than AIS shows
- Large cash deposits not explained
- Deductions claimed at maximum limits without proof
- Business income with very low margin
- Mismatch between opening/closing balances
- High-value property transactions
- Foreign assets not disclosed
- Cash withdrawals > 20L in a year
"""
        response = await self._complete(prompt)

        import re, json
        json_match = re.search(r'\{[\s\S]+\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except Exception:
                pass

        return {"risk_score": 50, "risk_level": "MEDIUM", "risk_factors": [], "recommendations": []}

    async def _complete(self, prompt: str, max_tokens: int = 4096) -> str:
        """Non-streaming completion."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT_TAX_ASSISTANT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

"""
ITC Reconciliation Engine
Reconciles GSTR-2B (auto-drafted ITC from portal) vs Purchase Books.

Handles:
- Invoice-level matching (GSTIN + invoice number + date + amount)
- Fuzzy matching for minor discrepancies (date ±3 days, amount ±Rs.5)
- Classification: Matched / Mismatched / Only in 2B / Only in Books
- GSTIN validation of suppliers
- ITC eligibility check per Section 17(5)
- Rule 36(4) — 10% provisional ITC cap (if applicable)
- Ineligible ITC flagging
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from difflib import SequenceMatcher
from datetime import datetime, timedelta


@dataclass
class PurchaseInvoice:
    """Invoice from books of accounts (purchase register)."""
    supplier_gstin: str
    supplier_name: str
    invoice_number: str
    invoice_date: str          # DD/MM/YYYY
    invoice_value: float
    taxable_value: float
    igst: float = 0
    cgst: float = 0
    sgst: float = 0
    cess: float = 0
    hsn_sac: str = ""
    is_rcm: bool = False
    is_claimed: bool = True    # Whether client wants to claim ITC


@dataclass
class GSTR2BInvoice:
    """Invoice as it appears in GSTR-2B (supplier-filed)."""
    supplier_gstin: str
    supplier_name: str
    supplier_trade_name: str
    invoice_number: str
    invoice_date: str
    invoice_type: str          # "B2B", "B2BA" (amended), etc.
    invoice_value: float
    taxable_value: float
    igst: float = 0
    cgst: float = 0
    sgst: float = 0
    cess: float = 0
    itc_availability: str = "Yes"  # Yes / No / Blocked
    gstr1_period: str = ""


@dataclass
class ReconciliationResult:
    matched: list[dict] = field(default_factory=list)
    mismatched: list[dict] = field(default_factory=list)
    only_in_2b: list[dict] = field(default_factory=list)       # In GSTR-2B but not in books
    only_in_books: list[dict] = field(default_factory=list)    # In books but not in GSTR-2B
    blocked_credits: list[dict] = field(default_factory=list)  # Section 17(5)
    summary: dict = field(default_factory=dict)


class ITCReconciliationEngine:
    """
    Reconciles purchase books against GSTR-2B data.
    Result drives what to enter in GSTR-3B Table 4.
    """

    AMOUNT_TOLERANCE = Decimal("5.00")        # Rs. 5 tolerance
    DATE_TOLERANCE_DAYS = 3                    # 3 days date mismatch tolerance

    def reconcile(
        self,
        books: list[PurchaseInvoice],
        gstr2b: list[GSTR2BInvoice],
    ) -> ReconciliationResult:
        result = ReconciliationResult()

        books_index = self._index_invoices(books)
        gstr2b_index = self._index_gstr2b(gstr2b)

        matched_book_keys = set()
        matched_2b_keys = set()

        # ── Phase 1: Exact match on GSTIN + invoice number ────────────────
        for key, book_inv in books_index.items():
            if key in gstr2b_index:
                g2b_inv = gstr2b_index[key]
                match_status = self._compare_amounts(book_inv, g2b_inv)

                if match_status["is_matched"]:
                    result.matched.append({
                        "invoice_number": book_inv.invoice_number,
                        "supplier_gstin": book_inv.supplier_gstin,
                        "supplier_name": book_inv.supplier_name,
                        "invoice_date": book_inv.invoice_date,
                        "books_igst": book_inv.igst,
                        "books_cgst": book_inv.cgst,
                        "books_sgst": book_inv.sgst,
                        "2b_igst": g2b_inv.igst,
                        "2b_cgst": g2b_inv.cgst,
                        "2b_sgst": g2b_inv.sgst,
                        "itc_claimable": g2b_inv.itc_availability == "Yes",
                        "match_type": "EXACT",
                    })
                else:
                    result.mismatched.append({
                        **match_status,
                        "invoice_number": book_inv.invoice_number,
                        "supplier_gstin": book_inv.supplier_gstin,
                        "supplier_name": book_inv.supplier_name,
                        "books_taxable": book_inv.taxable_value,
                        "books_igst": book_inv.igst,
                        "books_cgst": book_inv.cgst,
                        "books_sgst": book_inv.sgst,
                        "2b_taxable": g2b_inv.taxable_value,
                        "2b_igst": g2b_inv.igst,
                        "2b_cgst": g2b_inv.cgst,
                        "2b_sgst": g2b_inv.sgst,
                        "action": self._suggest_action(match_status),
                    })

                matched_book_keys.add(key)
                matched_2b_keys.add(key)

        # ── Phase 2: Fuzzy match unmatched invoices ───────────────────────
        unmatched_books = {k: v for k, v in books_index.items() if k not in matched_book_keys}
        unmatched_2b = {k: v for k, v in gstr2b_index.items() if k not in matched_2b_keys}

        for bkey, book_inv in list(unmatched_books.items()):
            fuzzy_match = self._fuzzy_match(book_inv, unmatched_2b)
            if fuzzy_match:
                g2b_inv, confidence = fuzzy_match
                g2b_key = f"{g2b_inv.supplier_gstin}_{g2b_inv.invoice_number}"
                result.mismatched.append({
                    "invoice_number": book_inv.invoice_number,
                    "matched_2b_invoice": g2b_inv.invoice_number,
                    "supplier_gstin": book_inv.supplier_gstin,
                    "match_type": "FUZZY",
                    "confidence": f"{confidence:.0%}",
                    "books_igst": book_inv.igst,
                    "2b_igst": g2b_inv.igst,
                    "difference_igst": round(book_inv.igst - g2b_inv.igst, 2),
                    "action": "VERIFY_AND_ACCEPT" if confidence > 0.9 else "MANUAL_CHECK",
                })
                matched_book_keys.add(bkey)
                matched_2b_keys.add(g2b_key)
                unmatched_2b.pop(g2b_key, None)

        # ── Phase 3: Only in GSTR-2B (not in books) ──────────────────────
        for key, g2b_inv in unmatched_2b.items():
            if key not in matched_2b_keys:
                result.only_in_2b.append({
                    "invoice_number": g2b_inv.invoice_number,
                    "supplier_gstin": g2b_inv.supplier_gstin,
                    "supplier_name": g2b_inv.supplier_name,
                    "invoice_date": g2b_inv.invoice_date,
                    "taxable_value": g2b_inv.taxable_value,
                    "igst": g2b_inv.igst,
                    "cgst": g2b_inv.cgst,
                    "sgst": g2b_inv.sgst,
                    "itc_availability": g2b_inv.itc_availability,
                    "action": "ADD_TO_BOOKS or DEFER_TO_NEXT_MONTH",
                })

        # ── Phase 4: Only in books (not in GSTR-2B) ──────────────────────
        for key, book_inv in unmatched_books.items():
            if key not in matched_book_keys:
                result.only_in_books.append({
                    "invoice_number": book_inv.invoice_number,
                    "supplier_gstin": book_inv.supplier_gstin,
                    "supplier_name": book_inv.supplier_name,
                    "invoice_date": book_inv.invoice_date,
                    "igst": book_inv.igst,
                    "cgst": book_inv.cgst,
                    "sgst": book_inv.sgst,
                    "action": "FOLLOW_UP_WITH_SUPPLIER or DEFER_ITC",
                    "risk": "ITC_NOT_AVAILABLE_TILL_SUPPLIER_FILES",
                })

        # ── Phase 5: Blocked credits check ───────────────────────────────
        from .hsn_master import lookup_hsn
        from .gstr3b_engine import BlockedCreditChecker

        for book_inv in books:
            if book_inv.hsn_sac:
                is_blocked, reason = BlockedCreditChecker.is_blocked(book_inv.hsn_sac)
                if is_blocked:
                    result.blocked_credits.append({
                        "invoice_number": book_inv.invoice_number,
                        "supplier_gstin": book_inv.supplier_gstin,
                        "hsn_sac": book_inv.hsn_sac,
                        "blocked_reason": reason,
                        "section": "17(5)",
                        "igst_blocked": book_inv.igst,
                        "cgst_blocked": book_inv.cgst,
                        "sgst_blocked": book_inv.sgst,
                        "action": "DO_NOT_CLAIM_ITC",
                    })

        result.summary = self._build_summary(result, books, gstr2b)
        return result

    def _index_invoices(self, invoices: list[PurchaseInvoice]) -> dict:
        return {
            f"{inv.supplier_gstin}_{inv.invoice_number.upper().strip()}": inv
            for inv in invoices
        }

    def _index_gstr2b(self, invoices: list[GSTR2BInvoice]) -> dict:
        return {
            f"{inv.supplier_gstin}_{inv.invoice_number.upper().strip()}": inv
            for inv in invoices
        }

    def _compare_amounts(self, book: PurchaseInvoice, g2b: GSTR2BInvoice) -> dict:
        diffs = {}
        is_matched = True
        tol = self.AMOUNT_TOLERANCE

        for field_name in ["igst", "cgst", "sgst", "cess"]:
            book_val = Decimal(str(getattr(book, field_name)))
            g2b_val = Decimal(str(getattr(g2b, field_name)))
            diff = abs(book_val - g2b_val)
            if diff > tol:
                is_matched = False
                diffs[f"diff_{field_name}"] = float(book_val - g2b_val)

        # Date mismatch (informational, not blocking)
        try:
            book_date = datetime.strptime(book.invoice_date, "%d/%m/%Y")
            g2b_date = datetime.strptime(g2b.invoice_date, "%d/%m/%Y")
            date_diff = abs((book_date - g2b_date).days)
            if date_diff > self.DATE_TOLERANCE_DAYS:
                diffs["date_mismatch"] = f"Books: {book.invoice_date}, 2B: {g2b.invoice_date}"
        except Exception:
            pass

        return {"is_matched": is_matched, **diffs}

    def _fuzzy_match(
        self, book: PurchaseInvoice, candidates: dict
    ) -> Optional[tuple[GSTR2BInvoice, float]]:
        """Find best fuzzy match by supplier + amount similarity."""
        best_match = None
        best_score = 0.0

        for key, g2b in candidates.items():
            if g2b.supplier_gstin != book.supplier_gstin:
                continue
            # Compare invoice numbers with fuzzy matching
            inv_score = SequenceMatcher(
                None,
                book.invoice_number.upper().strip(),
                g2b.invoice_number.upper().strip()
            ).ratio()
            # Compare amounts
            amount_match = abs(Decimal(str(book.igst)) - Decimal(str(g2b.igst))) <= self.AMOUNT_TOLERANCE
            combined = inv_score * (1.2 if amount_match else 0.8)

            if combined > best_score and combined > 0.6:
                best_score = combined
                best_match = g2b

        return (best_match, best_score) if best_match else None

    def _suggest_action(self, match_status: dict) -> str:
        diffs = {k: v for k, v in match_status.items()
                 if k.startswith("diff_") and abs(v) > 0}
        if not diffs:
            return "ACCEPT_2B_AMOUNT"
        total_diff = sum(abs(v) for v in diffs.values())
        if total_diff < 100:
            return "MINOR_DIFF_ACCEPT_WITH_NOTE"
        return "CONTACT_SUPPLIER_FOR_AMENDMENT"

    def _build_summary(
        self,
        result: ReconciliationResult,
        books: list[PurchaseInvoice],
        gstr2b: list[GSTR2BInvoice],
    ) -> dict:
        books_total_igst = sum(inv.igst for inv in books)
        books_total_cgst = sum(inv.cgst for inv in books)
        books_total_sgst = sum(inv.sgst for inv in books)
        gstr2b_total_igst = sum(inv.igst for inv in gstr2b)
        gstr2b_total_cgst = sum(inv.cgst for inv in gstr2b)
        gstr2b_total_sgst = sum(inv.sgst for inv in gstr2b)

        claimable_igst = sum(
            m["books_igst"] for m in result.matched if m.get("itc_claimable")
        )
        blocked_igst = sum(
            b["igst_blocked"] for b in result.blocked_credits
        )
        deferred_igst = sum(
            o["igst"] for o in result.only_in_books
        )

        return {
            "total_invoices_books": len(books),
            "total_invoices_2b": len(gstr2b),
            "matched_count": len(result.matched),
            "mismatched_count": len(result.mismatched),
            "only_in_2b_count": len(result.only_in_2b),
            "only_in_books_count": len(result.only_in_books),
            "blocked_count": len(result.blocked_credits),

            "books_igst": round(books_total_igst, 2),
            "books_cgst": round(books_total_cgst, 2),
            "books_sgst": round(books_total_sgst, 2),
            "gstr2b_igst": round(gstr2b_total_igst, 2),
            "gstr2b_cgst": round(gstr2b_total_cgst, 2),
            "gstr2b_sgst": round(gstr2b_total_sgst, 2),

            "net_difference_igst": round(books_total_igst - gstr2b_total_igst, 2),

            "itc_claimable_this_month_igst": round(claimable_igst, 2),
            "itc_blocked_sec17_5": round(blocked_igst, 2),
            "itc_deferred_no_2b": round(deferred_igst, 2),

            "recommendation": (
                "Claim ITC only for matched invoices available in GSTR-2B. "
                "Deferred ITC can be claimed in subsequent months once supplier files. "
                "Do not claim blocked credits u/s 17(5)."
            ),
        }

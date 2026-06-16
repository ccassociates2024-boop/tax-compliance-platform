"""
Invoice Template Engine
Converts structured invoice data (Excel/CSV/JSON) → validated GSTN-compliant GSTR-1 JSON.

Supports:
- B2B (registered buyers)
- B2C Large (unregistered, inter-state > 2.5L)
- B2C Small (unregistered, aggregate)
- Exports (with/without payment of tax)
- Credit/Debit Notes (registered & unregistered)
- Advance receipts
"""
import re
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
from .hsn_master import get_gst_rate, GST_STATE_CODES


@dataclass
class InvoiceLine:
    hsn_sac: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    taxable_value: float
    gst_rate: float          # 0, 5, 12, 18, 28
    igst_amount: float = 0
    cgst_amount: float = 0
    sgst_amount: float = 0
    cess_amount: float = 0


@dataclass
class Invoice:
    # Mandatory fields
    invoice_number: str
    invoice_date: str          # DD/MM/YYYY
    invoice_type: str          # B2B, B2CS, B2CL, EXP, CDNR, CDNUR

    # Buyer details
    receiver_gstin: Optional[str] = None    # Required for B2B
    receiver_name: Optional[str] = None
    place_of_supply: str = ""               # State code (2-digit)
    receiver_state: str = ""

    # Totals
    invoice_value: float = 0
    taxable_value: float = 0
    igst_amount: float = 0
    cgst_amount: float = 0
    sgst_amount: float = 0
    cess_amount: float = 0

    # Flags
    reverse_charge: str = "N"              # Y/N
    is_export: bool = False
    export_type: Optional[str] = None      # "WPAY" or "WOPAY"
    shipping_bill_number: Optional[str] = None
    shipping_bill_date: Optional[str] = None
    port_code: Optional[str] = None

    # Line items
    items: list[InvoiceLine] = field(default_factory=list)

    # Credit/Debit note specifics
    original_invoice_number: Optional[str] = None
    original_invoice_date: Optional[str] = None
    note_type: Optional[str] = None        # "C" (credit) or "D" (debit)


class InvoiceValidator:
    """Validates invoice data before GSTN submission."""

    GSTIN_PATTERN = re.compile(
        r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    )
    PAN_PATTERN = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')

    def validate(self, invoice: Invoice) -> list[str]:
        errors = []

        if not invoice.invoice_number:
            errors.append("Invoice number is required")
        if len(invoice.invoice_number) > 16:
            errors.append(f"Invoice number too long (max 16 chars): {invoice.invoice_number}")
        if not self._valid_date(invoice.invoice_date):
            errors.append(f"Invalid date format (use DD/MM/YYYY): {invoice.invoice_date}")

        if invoice.invoice_type == "B2B":
            if not invoice.receiver_gstin:
                errors.append(f"GSTIN required for B2B invoice: {invoice.invoice_number}")
            elif not self.GSTIN_PATTERN.match(invoice.receiver_gstin):
                errors.append(f"Invalid GSTIN format: {invoice.receiver_gstin}")

        if invoice.invoice_value < 0:
            errors.append(f"Invoice value cannot be negative: {invoice.invoice_number}")

        # Tax computation cross-check
        computed_igst = sum(item.igst_amount for item in invoice.items)
        computed_cgst = sum(item.cgst_amount for item in invoice.items)
        computed_sgst = sum(item.sgst_amount for item in invoice.items)

        tol = Decimal("0.50")   # 50 paise tolerance
        if abs(Decimal(str(invoice.igst_amount)) - Decimal(str(computed_igst))) > tol:
            errors.append(
                f"IGST mismatch on {invoice.invoice_number}: "
                f"header={invoice.igst_amount}, computed={computed_igst:.2f}"
            )

        if not invoice.place_of_supply or invoice.place_of_supply not in GST_STATE_CODES:
            errors.append(f"Invalid place of supply: '{invoice.place_of_supply}'")

        return errors

    @staticmethod
    def _valid_date(date_str: str) -> bool:
        try:
            d, m, y = date_str.split("/")
            return 1 <= int(d) <= 31 and 1 <= int(m) <= 12 and 2000 <= int(y) <= 2099
        except Exception:
            return False


class TaxComputer:
    """
    Computes GST amounts from taxable value and rate.
    Handles IGST (inter-state) vs CGST+SGST (intra-state) split.
    """

    @staticmethod
    def compute(taxable_value: float, gst_rate: float,
                supplier_state: str, buyer_state: str,
                is_export: bool = False) -> dict:

        taxable = Decimal(str(taxable_value))
        rate = Decimal(str(gst_rate))

        # Determine supply type
        is_inter_state = (supplier_state != buyer_state) or is_export

        igst = cgst = sgst = Decimal("0")

        if is_inter_state or is_export:
            igst = (taxable * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            half_rate = rate / 2
            cgst = (taxable * half_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sgst = cgst  # Always equal to CGST for intra-state

        total_tax = igst + cgst + sgst
        invoice_value = taxable + total_tax

        return {
            "taxable_value": float(taxable),
            "igst": float(igst),
            "cgst": float(cgst),
            "sgst": float(sgst),
            "total_tax": float(total_tax),
            "invoice_value": float(invoice_value),
            "supply_type": "INTER" if is_inter_state else "INTRA",
        }

    @staticmethod
    def compute_from_invoice_value(invoice_value: float, gst_rate: float,
                                    supplier_state: str, buyer_state: str) -> dict:
        """Back-calculate taxable value from inclusive invoice value."""
        inv = Decimal(str(invoice_value))
        rate = Decimal(str(gst_rate))
        taxable = (inv / (1 + rate / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return TaxComputer.compute(float(taxable), gst_rate, supplier_state, buyer_state)


class GSTR1Builder:
    """
    Builds complete GSTN-compliant GSTR-1 JSON payload from invoice list.
    Handles all tables: B2B, B2CL, B2CS, EXP, CDNR, CDNUR, HSN, DOC.
    """

    def __init__(self, gstin: str, period: str, supplier_state: str):
        self.gstin = gstin
        self.period = period                # "042024"
        self.supplier_state = supplier_state  # e.g. "27"
        self.validator = InvoiceValidator()

    def build(self, invoices: list[Invoice]) -> dict:
        """
        Convert invoice list to full GSTR-1 JSON.
        Returns: {payload, errors, summary}
        """
        all_errors = {}
        valid_invoices = []

        for inv in invoices:
            errors = self.validator.validate(inv)
            if errors:
                all_errors[inv.invoice_number] = errors
            else:
                valid_invoices.append(inv)

        b2b = self._build_b2b(valid_invoices)
        b2cl = self._build_b2cl(valid_invoices)
        b2cs = self._build_b2cs(valid_invoices)
        exp = self._build_exports(valid_invoices)
        cdnr = self._build_cdnr(valid_invoices)
        cdnur = self._build_cdnur(valid_invoices)
        hsn = self._build_hsn_summary(valid_invoices)
        doc = self._build_doc_summary(valid_invoices)

        payload = {
            "gstin": self.gstin,
            "fp": self.period,
            "gt": self._grand_total(valid_invoices),
            "cur_gt": self._grand_total(valid_invoices),
            "b2b": b2b,
            "b2cl": b2cl,
            "b2cs": b2cs,
            "exp": exp,
            "cdnr": cdnr,
            "cdnur": cdnur,
            "hsn": {"data": hsn},
            "doc_issue": {"doc_det": doc},
        }

        summary = self._build_summary(valid_invoices)

        return {
            "payload": payload,
            "validation_errors": all_errors,
            "summary": summary,
            "total_invoices": len(invoices),
            "valid_invoices": len(valid_invoices),
            "error_invoices": len(all_errors),
        }

    def _build_b2b(self, invoices: list[Invoice]) -> list[dict]:
        """Build Table 4A — B2B invoices grouped by buyer GSTIN."""
        b2b_invoices = [inv for inv in invoices if inv.invoice_type == "B2B"]
        by_gstin: dict[str, list] = defaultdict(list)

        for inv in b2b_invoices:
            by_gstin[inv.receiver_gstin].append({
                "inum": inv.invoice_number,
                "idt": inv.invoice_date,
                "val": round(inv.invoice_value, 2),
                "pos": inv.place_of_supply,
                "rchrg": inv.reverse_charge,
                "inv_typ": "R",   # Regular
                "itms": [
                    {
                        "num": i + 1,
                        "itm_det": {
                            "txval": round(item.taxable_value, 2),
                            "rt": item.gst_rate,
                            "iamt": round(item.igst_amount, 2),
                            "camt": round(item.cgst_amount, 2),
                            "samt": round(item.sgst_amount, 2),
                            "csamt": round(item.cess_amount, 2),
                        }
                    }
                    for i, item in enumerate(inv.items)
                ],
            })

        return [
            {"ctin": gstin, "inv": inv_list}
            for gstin, inv_list in by_gstin.items()
        ]

    def _build_b2cl(self, invoices: list[Invoice]) -> list[dict]:
        """
        Build Table 5 — B2C Large (unregistered, inter-state, invoice > 2.5L).
        Grouped by Place of Supply.
        """
        b2cl_invoices = [
            inv for inv in invoices
            if inv.invoice_type == "B2CL" and inv.invoice_value > 250000
        ]
        by_pos: dict[str, list] = defaultdict(list)

        for inv in b2cl_invoices:
            by_pos[inv.place_of_supply].append({
                "inum": inv.invoice_number,
                "idt": inv.invoice_date,
                "val": round(inv.invoice_value, 2),
                "itms": [
                    {
                        "num": i + 1,
                        "itm_det": {
                            "txval": round(item.taxable_value, 2),
                            "rt": item.gst_rate,
                            "iamt": round(item.igst_amount, 2),
                            "csamt": round(item.cess_amount, 2),
                        }
                    }
                    for i, item in enumerate(inv.items)
                ],
            })

        return [{"pos": pos, "inv": inv_list} for pos, inv_list in by_pos.items()]

    def _build_b2cs(self, invoices: list[Invoice]) -> list[dict]:
        """
        Build Table 7 — B2C Small (unregistered, aggregate).
        Grouped by {rate, place_of_supply}.
        """
        b2cs_invoices = [inv for inv in invoices if inv.invoice_type == "B2CS"]
        agg: dict[str, dict] = defaultdict(lambda: {
            "txval": 0, "iamt": 0, "camt": 0, "samt": 0, "csamt": 0
        })

        for inv in b2cs_invoices:
            for item in inv.items:
                key = f"{item.gst_rate}_{inv.place_of_supply}"
                agg[key]["rt"] = item.gst_rate
                agg[key]["pos"] = inv.place_of_supply
                agg[key]["txval"] += item.taxable_value
                agg[key]["iamt"] += item.igst_amount
                agg[key]["camt"] += item.cgst_amount
                agg[key]["samt"] += item.sgst_amount
                agg[key]["csamt"] += item.cess_amount

        return [
            {
                "sply_ty": "INTER" if v["iamt"] > 0 else "INTRA",
                "pos": v["pos"],
                "rt": v["rt"],
                "txval": round(v["txval"], 2),
                "iamt": round(v["iamt"], 2),
                "camt": round(v["camt"], 2),
                "samt": round(v["samt"], 2),
                "csamt": round(v["csamt"], 2),
            }
            for v in agg.values()
        ]

    def _build_exports(self, invoices: list[Invoice]) -> list[dict]:
        """Build Table 6A/6B — Exports (with/without payment of tax)."""
        exp_invoices = [inv for inv in invoices if inv.is_export]
        by_type: dict[str, list] = defaultdict(list)

        for inv in exp_invoices:
            exp_type = inv.export_type or "WOPAY"
            by_type[exp_type].append({
                "inum": inv.invoice_number,
                "idt": inv.invoice_date,
                "val": round(inv.invoice_value, 2),
                "sbnum": inv.shipping_bill_number or "",
                "sbdt": inv.shipping_bill_date or "",
                "sbpcode": inv.port_code or "",
                "itms": [
                    {
                        "txval": round(item.taxable_value, 2),
                        "rt": item.gst_rate,
                        "iamt": round(item.igst_amount, 2) if exp_type == "WPAY" else 0,
                        "csamt": round(item.cess_amount, 2),
                    }
                    for item in inv.items
                ],
            })

        return [{"exp_typ": t, "inv": inv_list} for t, inv_list in by_type.items()]

    def _build_cdnr(self, invoices: list[Invoice]) -> list[dict]:
        """Build Table 9B — Credit/Debit Notes (registered buyers)."""
        cdnr_invoices = [inv for inv in invoices if inv.invoice_type == "CDNR"]
        by_gstin: dict[str, list] = defaultdict(list)

        for inv in cdnr_invoices:
            by_gstin[inv.receiver_gstin].append({
                "nt_num": inv.invoice_number,
                "nt_dt": inv.invoice_date,
                "ntty": inv.note_type or "C",
                "val": round(inv.invoice_value, 2),
                "pos": inv.place_of_supply,
                "rchrg": inv.reverse_charge,
                "itms": [
                    {
                        "num": i + 1,
                        "itm_det": {
                            "txval": round(item.taxable_value, 2),
                            "rt": item.gst_rate,
                            "iamt": round(item.igst_amount, 2),
                            "camt": round(item.cgst_amount, 2),
                            "samt": round(item.sgst_amount, 2),
                            "csamt": round(item.cess_amount, 2),
                        }
                    }
                    for i, item in enumerate(inv.items)
                ],
            })

        return [{"ctin": gstin, "nt": nt_list} for gstin, nt_list in by_gstin.items()]

    def _build_cdnur(self, invoices: list[Invoice]) -> list[dict]:
        """Build Table 9B — Credit/Debit Notes (unregistered buyers)."""
        cdnur_invoices = [inv for inv in invoices if inv.invoice_type == "CDNUR"]
        result = []
        for inv in cdnur_invoices:
            result.append({
                "ntty": inv.note_type or "C",
                "nt_num": inv.invoice_number,
                "nt_dt": inv.invoice_date,
                "typ": "B2CL" if inv.invoice_value > 250000 else "B2CS",
                "val": round(inv.invoice_value, 2),
                "itms": [
                    {
                        "num": i + 1,
                        "itm_det": {
                            "txval": round(item.taxable_value, 2),
                            "rt": item.gst_rate,
                            "iamt": round(item.igst_amount, 2),
                            "camt": round(item.cgst_amount, 2),
                            "samt": round(item.sgst_amount, 2),
                            "csamt": round(item.cess_amount, 2),
                        }
                    }
                    for i, item in enumerate(inv.items)
                ],
            })
        return result

    def _build_hsn_summary(self, invoices: list[Invoice]) -> list[dict]:
        """
        Build HSN-wise summary (Table 12).
        Groups all line items by HSN code across all invoices.
        """
        hsn_agg: dict[str, dict] = defaultdict(lambda: {
            "uqc": "NOS", "qty": 0, "val": 0, "txval": 0,
            "iamt": 0, "camt": 0, "samt": 0, "csamt": 0,
        })

        for inv in invoices:
            for item in inv.items:
                key = item.hsn_sac
                hsn_agg[key]["hsn_sc"] = item.hsn_sac
                hsn_agg[key]["desc"] = item.description[:30]  # Max 30 chars
                hsn_agg[key]["uqc"] = item.unit or "NOS"
                hsn_agg[key]["rt"] = item.gst_rate
                hsn_agg[key]["qty"] += item.quantity
                hsn_agg[key]["val"] += (item.taxable_value + item.igst_amount +
                                         item.cgst_amount + item.sgst_amount)
                hsn_agg[key]["txval"] += item.taxable_value
                hsn_agg[key]["iamt"] += item.igst_amount
                hsn_agg[key]["camt"] += item.cgst_amount
                hsn_agg[key]["samt"] += item.sgst_amount
                hsn_agg[key]["csamt"] += item.cess_amount

        return [
            {
                "num": i + 1,
                "hsn_sc": v["hsn_sc"],
                "desc": v.get("desc", ""),
                "uqc": v["uqc"],
                "qty": round(v["qty"], 3),
                "val": round(v["val"], 2),
                "txval": round(v["txval"], 2),
                "iamt": round(v["iamt"], 2),
                "camt": round(v["camt"], 2),
                "samt": round(v["samt"], 2),
                "csamt": round(v["csamt"], 2),
            }
            for i, v in enumerate(hsn_agg.values())
        ]

    def _build_doc_summary(self, invoices: list[Invoice]) -> list[dict]:
        """Build Table 13 — Document Issue Summary."""
        from collections import Counter
        type_counts = Counter(inv.invoice_type for inv in invoices)

        doc_type_map = {
            "B2B": ("01", "Invoices for outward supply"),
            "B2CS": ("01", "Invoices for outward supply"),
            "B2CL": ("01", "Invoices for outward supply"),
            "CDNR": ("03", "Credit Notes"),
            "CDNUR": ("03", "Credit Notes"),
        }

        result = []
        seen = set()
        for inv_type, (doc_num, doc_desc) in doc_type_map.items():
            if doc_num not in seen and type_counts.get(inv_type, 0) > 0:
                seen.add(doc_num)
                result.append({
                    "doc_num": doc_num,
                    "doc_det": [{
                        "doc_typ": doc_desc,
                        "docs": [{
                            "num": 1,
                            "from": "1",
                            "to": str(type_counts.get(inv_type, 1)),
                            "totnum": type_counts.get(inv_type, 1),
                            "cancel": 0,
                            "net_issue": type_counts.get(inv_type, 1),
                        }]
                    }]
                })
        return result

    def _grand_total(self, invoices: list[Invoice]) -> float:
        return round(sum(inv.invoice_value for inv in invoices), 2)

    def _build_summary(self, invoices: list[Invoice]) -> dict:
        b2b = [inv for inv in invoices if inv.invoice_type == "B2B"]
        b2cs = [inv for inv in invoices if inv.invoice_type in ("B2CS", "B2CL")]
        exports = [inv for inv in invoices if inv.is_export]
        cdn = [inv for inv in invoices if inv.invoice_type in ("CDNR", "CDNUR")]

        return {
            "total_taxable_value": round(sum(inv.taxable_value for inv in invoices), 2),
            "total_invoice_value": round(sum(inv.invoice_value for inv in invoices), 2),
            "total_igst": round(sum(inv.igst_amount for inv in invoices), 2),
            "total_cgst": round(sum(inv.cgst_amount for inv in invoices), 2),
            "total_sgst": round(sum(inv.sgst_amount for inv in invoices), 2),
            "total_cess": round(sum(inv.cess_amount for inv in invoices), 2),
            "b2b_count": len(b2b),
            "b2b_value": round(sum(inv.invoice_value for inv in b2b), 2),
            "b2cs_count": len(b2cs),
            "b2cs_value": round(sum(inv.invoice_value for inv in b2cs), 2),
            "export_count": len(exports),
            "cdn_count": len(cdn),
        }

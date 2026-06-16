"""
HSN / SAC Code Master
- HSN (Harmonised System of Nomenclature) for goods
- SAC (Services Accounting Code) for services
- GST rates: 0%, 0.25%, 1.5%, 3%, 5%, 12%, 18%, 28% + cess
- Includes: description, UQC, applicable cess

Rule: Turnover > 5 Cr → 6-digit HSN mandatory
      Turnover 1.5–5 Cr → 4-digit HSN
      Turnover < 1.5 Cr → 2-digit HSN (optional)
"""
from typing import Optional
from sqlalchemy import Column, String, Numeric, Boolean, Integer, Text
from sqlalchemy.orm import Session
import uuid

from database import Base
from db_types import GUID


class HSNCode(Base):
    __tablename__ = "hsn_codes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    hsn_code = Column(String(10), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    chapter = Column(String(2), nullable=False)       # First 2 digits
    heading = Column(String(4), nullable=False)       # First 4 digits

    # GST Rates
    igst_rate = Column(Numeric(5, 2), nullable=False)
    cgst_rate = Column(Numeric(5, 2), nullable=False)
    sgst_rate = Column(Numeric(5, 2), nullable=False)
    cess_rate = Column(Numeric(5, 2), default=0)

    # Product details
    uqc = Column(String(10), nullable=True)           # Unit Quantity Code
    is_service = Column(Boolean, default=False)        # True if SAC code
    is_exempt = Column(Boolean, default=False)
    is_nil_rated = Column(Boolean, default=False)

    # Reverse charge
    reverse_charge_applicable = Column(Boolean, default=False)


class SACCode(Base):
    __tablename__ = "sac_codes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    sac_code = Column(String(10), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    igst_rate = Column(Numeric(5, 2), nullable=False)
    cgst_rate = Column(Numeric(5, 2), nullable=False)
    sgst_rate = Column(Numeric(5, 2), nullable=False)
    is_exempt = Column(Boolean, default=False)
    reverse_charge_applicable = Column(Boolean, default=False)


# ─── In-memory HSN lookup (common codes — full DB seeded separately) ──────────

COMMON_HSN = {
    # Chapter 01-05: Live animals & animal products
    "0101": {"desc": "Live horses, asses, mules", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "NOS"},
    "0201": {"desc": "Meat of bovine animals, fresh or chilled", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "KGS"},

    # Chapter 07: Vegetables
    "0701": {"desc": "Potatoes, fresh or chilled", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "KGS"},
    "0702": {"desc": "Tomatoes, fresh or chilled", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "KGS"},

    # Chapter 08: Fruits
    "0801": {"desc": "Coconuts, Brazil nuts, cashew nuts", "igst": 5, "cgst": 2.5, "sgst": 2.5, "uqc": "KGS"},
    "0803": {"desc": "Bananas, including plantains", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "KGS"},

    # Chapter 10: Cereals
    "1001": {"desc": "Wheat and meslin", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "KGS"},
    "1006": {"desc": "Rice", "igst": 5, "cgst": 2.5, "sgst": 2.5, "uqc": "KGS"},

    # Chapter 17: Sugar
    "1701": {"desc": "Cane or beet sugar", "igst": 5, "cgst": 2.5, "sgst": 2.5, "uqc": "KGS"},

    # Chapter 22: Beverages
    "2201": {"desc": "Waters including mineral waters", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "LTR"},
    "2202": {"desc": "Waters with added sugar (aerated)", "igst": 28, "cgst": 14, "sgst": 14, "uqc": "LTR"},

    # Chapter 27: Mineral fuels
    "2710": {"desc": "Petroleum oils", "igst": 0, "cgst": 0, "sgst": 0, "uqc": "LTR"},  # Outside GST
    "2711": {"desc": "Petroleum gases (LPG)", "igst": 5, "cgst": 2.5, "sgst": 2.5, "uqc": "KGS"},

    # Chapter 28-29: Chemicals
    "2836": {"desc": "Carbonates, sodium bicarbonate", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "KGS"},

    # Chapter 30: Pharmaceuticals
    "3004": {"desc": "Medicaments for retail sale", "igst": 12, "cgst": 6, "sgst": 6, "uqc": "NOS"},
    "3005": {"desc": "Wadding, gauze, bandages", "igst": 12, "cgst": 6, "sgst": 6, "uqc": "NOS"},

    # Chapter 39: Plastics
    "3901": {"desc": "Polymers of ethylene", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "KGS"},
    "3923": {"desc": "Plastic articles for packing", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},

    # Chapter 48: Paper
    "4802": {"desc": "Uncoated paper for writing", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "KGS"},
    "4819": {"desc": "Cartons, boxes of paper/paperboard", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},

    # Chapter 61-62: Apparel
    "6101": {"desc": "Men's overcoats of textile", "igst": 12, "cgst": 6, "sgst": 6, "uqc": "NOS"},
    "6201": {"desc": "Men's anoraks, windcheaters", "igst": 12, "cgst": 6, "sgst": 6, "uqc": "NOS"},
    "6110": {"desc": "Jerseys, pullovers (value ≤ 1000)", "igst": 5, "cgst": 2.5, "sgst": 2.5, "uqc": "NOS"},

    # Chapter 64: Footwear
    "6401": {"desc": "Waterproof footwear", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "PAIRS"},
    "6403": {"desc": "Footwear with outer soles of rubber", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "PAIRS"},

    # Chapter 73: Iron/Steel
    "7308": {"desc": "Structures of iron/steel", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "KGS"},
    "7317": {"desc": "Nails, tacks, staples of iron/steel", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "KGS"},

    # Chapter 84-85: Machinery & Electronics
    "8415": {"desc": "Air conditioning machines", "igst": 28, "cgst": 14, "sgst": 14, "uqc": "NOS"},
    "8418": {"desc": "Refrigerators, freezers", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},
    "8471": {"desc": "Automatic data processing machines (computers)", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},
    "8517": {"desc": "Telephone sets, smartphones", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},
    "8528": {"desc": "Monitors, projectors, TV sets", "igst": 28, "cgst": 14, "sgst": 14, "uqc": "NOS"},

    # Chapter 87: Vehicles
    "8703": {"desc": "Motor cars and vehicles for persons", "igst": 28, "cgst": 14, "sgst": 14, "cess": 17, "uqc": "NOS"},
    "8711": {"desc": "Motorcycles", "igst": 28, "cgst": 14, "sgst": 14, "cess": 3, "uqc": "NOS"},

    # Chapter 90: Optical instruments
    "9006": {"desc": "Photographic cameras", "igst": 18, "cgst": 9, "sgst": 9, "uqc": "NOS"},

    # Chapter 99: Services
    "9954": {"desc": "Construction services", "igst": 18, "cgst": 9, "sgst": 9},
    "9983": {"desc": "Other professional/technical services", "igst": 18, "cgst": 9, "sgst": 9},
    "9985": {"desc": "Support services (manpower supply)", "igst": 18, "cgst": 9, "sgst": 9},
    "9992": {"desc": "Education services", "igst": 0, "cgst": 0, "sgst": 0},
    "9993": {"desc": "Health care services", "igst": 0, "cgst": 0, "sgst": 0},
    "9997": {"desc": "Other services", "igst": 18, "cgst": 9, "sgst": 9},
}

# UQC Master (Unit Quantity Codes as per GSTN)
UQC_CODES = {
    "BAG": "Bag",
    "BAL": "Bale",
    "BDL": "Bundle",
    "BKL": "Buckle",
    "BOU": "Billion of Units",
    "BOX": "Box",
    "BTL": "Bottle",
    "BUN": "Bunch",
    "CAN": "Can",
    "CBM": "Cubic Meter",
    "CCM": "Cubic Centimeter",
    "CMS": "Centimeter",
    "CTN": "Carton",
    "DOZ": "Dozen",
    "DRM": "Drum",
    "GGS": "Great Gross (12 Doz.)",
    "GMS": "Grammes",
    "GRS": "Gross",
    "GYD": "Gross Yards",
    "KGS": "Kilogrammes",
    "KLR": "Kilolitre",
    "KME": "Kilometre",
    "LTR": "Litre",
    "MLT": "Millilitre",
    "MTR": "Metre",
    "MTS": "Metric Ton",
    "NOS": "Numbers",
    "OTH": "Others",
    "PAC": "Pack",
    "PCS": "Pieces",
    "PRS": "Pairs",
    "QTL": "Quintal",
    "ROL": "Roll",
    "SET": "Set",
    "SQF": "Square Feet",
    "SQM": "Square Meter",
    "SQY": "Square Yards",
    "TBS": "Tablets",
    "TGM": "Ten Grammes",
    "THD": "Thousands",
    "TON": "Tons",
    "TUB": "Tube",
    "UGS": "US Gallons",
    "UNT": "Units",
    "YDS": "Yards",
}

# GST State codes
GST_STATE_CODES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh (New)",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}


def lookup_hsn(hsn_code: str) -> Optional[dict]:
    """Look up HSN/SAC code — tries 8, 6, 4, 2 digit variants."""
    for digits in [8, 6, 4, 2]:
        key = hsn_code[:digits]
        if key in COMMON_HSN:
            return {**COMMON_HSN[key], "hsn_code": key, "matched_digits": digits}
    return None


def get_gst_rate(hsn_code: str) -> dict:
    """Get IGST/CGST/SGST rates for an HSN code."""
    result = lookup_hsn(hsn_code)
    if result:
        return {
            "igst": float(result.get("igst", 18)),
            "cgst": float(result.get("cgst", 9)),
            "sgst": float(result.get("sgst", 9)),
            "cess": float(result.get("cess", 0)),
        }
    return {"igst": 18, "cgst": 9, "sgst": 9, "cess": 0}   # Default 18%


def suggest_hsn(keyword: str) -> list[dict]:
    """Search HSN by description keyword."""
    keyword = keyword.lower()
    results = []
    for code, data in COMMON_HSN.items():
        if keyword in data["desc"].lower():
            results.append({
                "hsn_code": code,
                "description": data["desc"],
                "igst_rate": data["igst"],
                "uqc": data.get("uqc", "NOS"),
            })
    return results[:10]

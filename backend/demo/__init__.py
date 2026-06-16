"""
Demo / Sandbox mode for TaxCompliance AI Platform.

When DEMO_MODE=True:
  - A pre-seeded demo CA account is available (demo@taxcomplianceai.in / demo123)
  - 5 realistic demo clients are seeded with full tax data
  - AI responses return canned answers (no Anthropic API call)
  - Portal fetch returns mock Form 26AS / GSTR-2B / TDS data
  - Razorpay returns a simulated payment success
  - A demo banner is shown in the frontend
"""
from .seed import seed_demo_data
from .mock_data import DEMO_CLIENTS, get_mock_itr_result, get_mock_gst_result, get_mock_tds_result, get_mock_ai_response

__all__ = [
    "seed_demo_data",
    "DEMO_CLIENTS",
    "get_mock_itr_result",
    "get_mock_gst_result",
    "get_mock_tds_result",
    "get_mock_ai_response",
]

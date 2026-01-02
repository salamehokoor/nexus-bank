"""
AI Business Advisor integration using Google Gemini.

This module provides READ-ONLY decision support for administrators.
The AI analyzes aggregated business metrics and provides:
- Performance explanations
- Risk signals
- Descriptive recommendations (requiring human review)

The AI does NOT:
- Modify balances, transactions, or any data
- Trigger automated actions
- Make autonomous decisions
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Model configuration
AI_MODEL_NAME = "gemini-2.5-flash"


def analyze_business(report_text: str, report_json: dict) -> str | None:
    """
    Analyze business metrics using Google Gemini AI.

    This function is READ-ONLY and provides decision support only.
    All recommendations require human review before action.

    Args:
        report_text: Human-readable business report summary
        report_json: Structured metrics data (dict)

    Returns:
        AI-generated analysis text, or None if:
        - GEMINI_API_KEY is not configured
        - API call fails for any reason

    The endpoint will return HTTP 200 with ai_analysis=null on failure.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY not configured. Skipping AI business analysis."
        )
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Build the AI Business Advisor prompt
        prompt = _build_advisor_prompt(report_text, report_json)

        response = client.models.generate_content(
            model=AI_MODEL_NAME,
            contents=prompt
        )

        logger.info("AI Business Advisor analysis completed successfully.")
        return response.text

    except Exception as e:
        logger.error(f"AI Business Advisor analysis failed: {e}")
        return None


def _build_advisor_prompt(report_text: str, report_json: dict) -> str:
    """
    Build a strict, professional prompt for the AI Business Advisor.

    The prompt enforces:
    - Professional, conservative tone
    - No speculation beyond provided data
    - No automated action recommendations
    - Clear scope limitations
    """
    json_formatted = json.dumps(report_json, indent=2, default=str)

    prompt = f"""You are an AI Business Advisor for a digital banking analytics platform.

IMPORTANT CONSTRAINTS:
- You are providing READ-ONLY decision support for administrators.
- All financial values represent business indicators in a banking simulation, NOT real money.
- You must NOT suggest automated changes, enforcement actions, or system modifications.
- All recommendations must be DESCRIPTIVE and require HUMAN REVIEW.
- Do NOT speculate beyond the data provided.
- If data is insufficient, state that explicitly.

YOUR ROLE:
1. Explain significant performance changes (profit, revenue, users, transactions)
2. Identify business risks (loss days, high failure rates, efficiency issues)
3. Provide clear, actionable suggestions for administrators to INVESTIGATE

OUTPUT FORMAT:
📊 **Performance Summary**
[Short natural-language explanation of key metrics]

🔍 **Key Observations**
[Bullet points with data-backed insights]

⚠️ **Risk Signals**
[Loss days, unusual patterns, inefficiencies identified]

💡 **Recommendations for Review**
[Clear suggestions for what administrators should investigate - NOT automated actions]

---

BUSINESS REPORT (Natural Language):
{report_text}

---

STRUCTURED METRICS DATA (JSON):
{json_formatted}

---

Provide your analysis now. Be professional, data-driven, and conservative.
"""
    return prompt

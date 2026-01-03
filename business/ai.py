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


def explain_daily_performance(target_date) -> str | None:
    """
    Generate AI insight comparing target_date metrics to the previous day.

    This function:
    1. Fetches metrics for target_date and target_date - 1 day
    2. Builds a comparison prompt
    3. Calls Gemini API for analysis
    4. Saves the insight to the DailyBusinessMetrics model

    Args:
        target_date: The date to analyze (date object)

    Returns:
        AI-generated insight text, or None if unavailable
    """
    from datetime import timedelta
    from .models import DailyBusinessMetrics

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY not configured. Skipping daily performance analysis."
        )
        return None

    try:
        # Fetch today's and yesterday's metrics
        today_metrics = DailyBusinessMetrics.objects.filter(date=target_date).first()
        yesterday = target_date - timedelta(days=1)
        yesterday_metrics = DailyBusinessMetrics.objects.filter(date=yesterday).first()

        if not today_metrics:
            logger.warning(f"No metrics found for {target_date}")
            return None

        # Build comparison data
        today_data = _metrics_to_dict(today_metrics)
        yesterday_data = _metrics_to_dict(yesterday_metrics) if yesterday_metrics else None

        # Build prompt
        prompt = _build_comparison_prompt(target_date, today_data, yesterday, yesterday_data)

        # Call Gemini API
        from google import genai
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=AI_MODEL_NAME,
            contents=prompt
        )

        insight = response.text

        # Save to model
        today_metrics.ai_insight = insight
        today_metrics.save(update_fields=["ai_insight"])

        logger.info(f"AI daily performance insight generated for {target_date}")
        return insight

    except Exception as e:
        logger.error(f"AI daily performance analysis failed: {e}")
        return None


def _metrics_to_dict(metrics) -> dict:
    """Convert DailyBusinessMetrics to a dict for prompting."""
    if not metrics:
        return {}
    return {
        "date": str(metrics.date),
        "new_users": metrics.new_users,
        "total_users": metrics.total_users,
        "active_users": metrics.active_users,
        "total_transactions_success": metrics.total_transactions_success,
        "total_transactions_failed": metrics.total_transactions_failed,
        "total_transferred_amount": str(metrics.total_transferred_amount),
        "avg_transaction_value": str(metrics.avg_transaction_value),
        "bill_payments_count": metrics.bill_payments_count,
        "bill_payments_amount": str(metrics.bill_payments_amount),
        "fee_revenue": str(metrics.fee_revenue),
        "net_revenue": str(metrics.net_revenue),
        "profit": str(metrics.profit),
        "failed_logins": metrics.failed_logins,
        "incidents": metrics.incidents,
    }


def _build_comparison_prompt(today_date, today_data: dict, yesterday_date, yesterday_data: dict | None) -> str:
    """Build a prompt for comparing two days of metrics."""
    today_json = json.dumps(today_data, indent=2)

    if yesterday_data:
        yesterday_json = json.dumps(yesterday_data, indent=2)
        comparison_context = f"""
YESTERDAY ({yesterday_date}) METRICS:
{yesterday_json}

TODAY ({today_date}) METRICS:
{today_json}
"""
    else:
        comparison_context = f"""
TODAY ({today_date}) METRICS:
{today_json}

Note: No data available for the previous day ({yesterday_date}).
"""

    prompt = f"""You are an AI Business Advisor for a digital banking executive dashboard.

TASK: Compare today's banking metrics with yesterday's and explain the changes in plain English.

IMPORTANT CONSTRAINTS:
- Be concise and executive-friendly (2-3 paragraphs max)
- Focus on the most significant changes
- Use simple language, avoid technical jargon
- Highlight both positive and concerning trends
- Do NOT suggest automated actions

{comparison_context}

Provide a brief, professional summary suitable for an executive dashboard. Format:

📊 **Daily Performance Summary**
[2-3 sentences on overall performance]

📈 **Key Changes**
[Bullet points of significant changes with percentages if applicable]

⚠️ **Points of Attention** (if any)
[Brief note on concerning trends, or "No significant concerns" if positive]
"""
    return prompt

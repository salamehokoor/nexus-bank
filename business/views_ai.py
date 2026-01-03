"""
AI Business Advisor API views.

This module provides a READ-ONLY decision support endpoint for administrators.
The AI analyzes aggregated business metrics and provides insights.

Security:
- Admin/superuser access only (IsAdminUser permission)
- Read-only operations on aggregated data
- No modifications to balances, transactions, or policies

Failure Behavior:
- If GEMINI_API_KEY is missing: returns HTTP 200 with ai_analysis=null
- If Gemini API fails: returns HTTP 200 with ai_analysis=null
- Errors are logged but never exposed to clients as 500
"""
import logging
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema, OpenApiExample

from .ai import analyze_business, explain_daily_performance, AI_MODEL_NAME
from .models import DailyAIInsight, MonthlyAIInsight, DailyBusinessMetrics
from .reporting import generate_daily_report, generate_monthly_report
from .serializers_ai import (
    AIAdvisorRequestSerializer,
    AIAdvisorResponseSerializer,
)

logger = logging.getLogger(__name__)


class DailyInsightTriggerView(APIView):
    """
    POST /business/ai/daily-insight/
    
    Trigger AI analysis comparing today's metrics with yesterday's.
    The insight is saved to DailyBusinessMetrics.ai_insight and returned.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Generate Daily AI Insight",
        description="Compare today's metrics with yesterday and generate AI insight.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date", "example": "2026-01-03"}
                },
                "required": ["date"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "ai_insight": {"type": "string", "nullable": True},
                }
            }
        },
        tags=["Business Intelligence"],
    )
    def post(self, request):
        date_str = request.data.get("date")
        if not date_str:
            return Response(
                {"detail": "date field is required (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from datetime import datetime
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Trigger AI insight generation
        insight = explain_daily_performance(target_date)

        # Fetch the metrics to return the saved insight
        metrics = DailyBusinessMetrics.objects.filter(date=target_date).first()

        return Response({
            "date": str(target_date),
            "ai_insight": insight,
            "saved": metrics.ai_insight is not None if metrics else False,
        })


class AIBusinessAdvisorView(APIView):
    """
    AI Business Advisor endpoint for admin decision support.

    This endpoint is:
    - Admin-only (requires staff/superuser status)
    - Read-only (does not modify any data)
    - Provides AI-generated insights based on aggregated metrics

    The AI:
    - Explains performance trends
    - Identifies risk signals
    - Provides descriptive recommendations

    All recommendations require human review before action.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="AI Business Advisor",
        description="""
Generate AI-powered business insights for administrators.

**Access Control:** Admin/superuser only.

**Scope:** Read-only analysis of aggregated metrics. Does NOT modify:
- Account balances
- Transactions
- Fee structures
- Risk policies

**Output:** AI-generated explanations, risk signals, and recommendations.
All recommendations are descriptive and require human review.

**Failure Behavior:** If AI is unavailable (missing API key or API error),
returns HTTP 200 with `ai_analysis: null`. No 500 errors.
        """,
        request=AIAdvisorRequestSerializer,
        responses={
            200: AIAdvisorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                name="Daily Analysis Request",
                value={
                    "period_type": "daily",
                    "date": "2025-12-04",
                },
                request_only=True,
            ),
            OpenApiExample(
                name="Monthly Analysis Request",
                value={
                    "period_type": "monthly",
                    "month": "2025-12-01",
                },
                request_only=True,
            ),
            OpenApiExample(
                name="Successful Response with AI Analysis",
                value={
                    "period_type": "daily",
                    "date_or_month": "2025-12-04",
                    "model": "gemini-2.5-flash",
                    "report_text": "NEXUS BANK BUSINESS METRICS REPORT...",
                    "report_json": {
                        "date_range": {"from": "2025-11-04", "to": "2025-12-04"},
                        "totals": {"profit": 500.00, "new_users": 150},
                        "ratios": {"transaction_success_rate_pct": 97.5},
                    },
                    "ai_analysis": "📊 **Performance Summary**\n\nThe platform shows healthy growth...",
                },
                response_only=True,
            ),
            OpenApiExample(
                name="Response when AI Unavailable",
                value={
                    "period_type": "daily",
                    "date_or_month": "2025-12-04",
                    "model": "gemini-2.5-flash",
                    "report_text": "NEXUS BANK BUSINESS METRICS REPORT...",
                    "report_json": {
                        "date_range": {"from": "2025-11-04", "to": "2025-12-04"},
                        "totals": {"profit": 500.00},
                    },
                    "ai_analysis": None,
                },
                response_only=True,
            ),
        ],
        tags=["Business Intelligence"],
    )
    def post(self, request):
        """
        Generate and persist AI business analysis.

        Request body:
        - period_type: "daily" or "monthly" (required)
        - date: YYYY-MM-DD for daily reports
        - month: YYYY-MM-01 for monthly reports

        Returns:
        - Always HTTP 200
        - ai_analysis is null if AI is unavailable
        """
        serializer = AIAdvisorRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        period_type = serializer.validated_data["period_type"]

        try:
            if period_type == "daily":
                return self._handle_daily_report(serializer.validated_data)
            else:
                return self._handle_monthly_report(serializer.validated_data)
        except Exception as e:
            logger.error(f"AI Business Advisor error: {e}")
            # Return 200 with null ai_analysis per requirements
            return Response({
                "period_type": period_type,
                "date_or_month": str(
                    serializer.validated_data.get("date") or
                    serializer.validated_data.get("month")
                ),
                "model": AI_MODEL_NAME,
                "report_text": "",
                "report_json": {},
                "ai_analysis": None,
            })

    def _handle_daily_report(self, validated_data):
        """Generate and persist daily AI insight."""
        target_date = validated_data["date"]

        # Generate deterministic report
        report_data = generate_daily_report(target_date)
        report_text = report_data["report_text"]
        report_json = report_data["report_json"]

        # Call AI analysis (returns None on failure)
        ai_output = analyze_business(report_text, report_json)

        # Persist (upsert)
        insight, created = DailyAIInsight.objects.update_or_create(
            date=target_date,
            defaults={
                "report_text": report_text,
                "report_json": report_json,
                "ai_output": ai_output,
                "model_name": AI_MODEL_NAME,
            }
        )

        logger.info(
            f"Daily AI Insight {'created' if created else 'updated'} for {target_date}"
        )

        return Response({
            "period_type": "daily",
            "date_or_month": target_date.isoformat(),
            "model": AI_MODEL_NAME,
            "report_text": report_text,
            "report_json": report_json,
            "ai_analysis": ai_output,
        })

    def _handle_monthly_report(self, validated_data):
        """Generate and persist monthly AI insight."""
        target_month = validated_data["month"]

        # Ensure it's the first day of the month
        target_month = target_month.replace(day=1)

        # Generate deterministic report
        report_data = generate_monthly_report(target_month)
        report_text = report_data["report_text"]
        report_json = report_data["report_json"]

        # Call AI analysis (returns None on failure)
        ai_output = analyze_business(report_text, report_json)

        # Persist (upsert)
        insight, created = MonthlyAIInsight.objects.update_or_create(
            month=target_month,
            defaults={
                "report_text": report_text,
                "report_json": report_json,
                "ai_output": ai_output,
                "model_name": AI_MODEL_NAME,
            }
        )

        logger.info(
            f"Monthly AI Insight {'created' if created else 'updated'} for {target_month}"
        )

        return Response({
            "period_type": "monthly",
            "date_or_month": target_month.isoformat(),
            "model": AI_MODEL_NAME,
            "report_text": report_text,
            "report_json": report_json,
            "ai_analysis": ai_output,
        })

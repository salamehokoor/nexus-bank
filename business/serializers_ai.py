"""
Serializers for AI Business Advisor endpoint.

These serializers define the request/response schema for the AI advisor API.
"""
from datetime import date

from rest_framework import serializers


class AIAdvisorRequestSerializer(serializers.Serializer):
    """
    Request schema for AI Business Advisor endpoint.

    Either 'date' (for daily) or 'month' (for monthly) must be provided
    based on the period_type.
    """

    PERIOD_CHOICES = [
        ("daily", "Daily Report"),
        ("monthly", "Monthly Report"),
    ]

    period_type = serializers.ChoiceField(
        choices=PERIOD_CHOICES,
        required=True,
        help_text="Type of report period: 'daily' or 'monthly'"
    )
    date = serializers.DateField(
        required=False,
        help_text="Target date for daily reports (YYYY-MM-DD)"
    )
    month = serializers.DateField(
        required=False,
        help_text="First day of target month for monthly reports (YYYY-MM-01)"
    )

    def validate(self, attrs):
        """Ensure the correct date field is provided for the period type."""
        period_type = attrs.get("period_type")

        if period_type == "daily":
            if not attrs.get("date"):
                raise serializers.ValidationError({
                    "date": "This field is required for daily reports."
                })
        elif period_type == "monthly":
            if not attrs.get("month"):
                raise serializers.ValidationError({
                    "month": "This field is required for monthly reports."
                })
            # Ensure month is first day
            month_value = attrs["month"]
            if month_value.day != 1:
                attrs["month"] = month_value.replace(day=1)

        return attrs


class AIAdvisorResponseSerializer(serializers.Serializer):
    """
    Response schema for AI Business Advisor endpoint.

    The ai_analysis field will be null if:
    - GEMINI_API_KEY is not configured
    - The AI API call fails for any reason
    """

    period_type = serializers.ChoiceField(
        choices=[("daily", "Daily"), ("monthly", "Monthly")],
        help_text="Type of report generated"
    )
    date_or_month = serializers.CharField(
        help_text="The date (YYYY-MM-DD) or month (YYYY-MM-01) analyzed"
    )
    model = serializers.CharField(
        help_text="AI model used for analysis (e.g., 'gemini-2.5-flash')"
    )
    report_text = serializers.CharField(
        help_text="Deterministic business report in human-readable format"
    )
    report_json = serializers.JSONField(
        help_text="Structured metrics summary as JSON"
    )
    ai_analysis = serializers.CharField(
        allow_null=True,
        help_text=(
            "AI-generated analysis text. "
            "Null if AI is unavailable (missing API key or API error)."
        )
    )


class DailyAIInsightSerializer(serializers.Serializer):
    """Serializer for DailyAIInsight model (read-only)."""

    id = serializers.IntegerField(read_only=True)
    date = serializers.DateField()
    report_text = serializers.CharField()
    report_json = serializers.JSONField()
    ai_output = serializers.CharField(allow_null=True)
    model_name = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class MonthlyAIInsightSerializer(serializers.Serializer):
    """Serializer for MonthlyAIInsight model (read-only)."""

    id = serializers.IntegerField(read_only=True)
    month = serializers.DateField()
    report_text = serializers.CharField()
    report_json = serializers.JSONField()
    ai_output = serializers.CharField(allow_null=True)
    model_name = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

"""
Business report generation services for AI Business Advisor.

These functions generate deterministic reports from aggregated metrics.
The reports are used as input for the AI Business Advisor analysis.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Sum, Count, F, Q
from django.utils import timezone

from .models import (
    DailyBusinessMetrics,
    CountryUserMetrics,
    CurrencyMetrics,
    WeeklySummary,
    MonthlySummary,
)


def _decimal_to_float(obj: Any) -> Any:
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def generate_business_report_json(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> Dict[str, Any]:
    """
    Generate a structured JSON summary of business metrics.

    Args:
        date_from: Start date for the report period (default: 90 days ago)
        date_to: End date for the report period (default: today)

    Returns:
        Dictionary containing:
        - date_range: period covered
        - totals: aggregate metrics
        - ratios: computed KPIs
        - top_countries: by users and revenue
        - top_currencies: by volume and revenue
        - loss_days: days with negative profit
        - weekly_summary: recent weekly trends
        - monthly_summary: recent monthly trends
    """
    # Default date range: last 90 days
    if date_to is None:
        date_to = timezone.localdate()
    if date_from is None:
        date_from = date_to - timedelta(days=90)

    # Fetch daily metrics for the period
    daily_qs = DailyBusinessMetrics.objects.filter(
        date__gte=date_from,
        date__lte=date_to
    )

    # Aggregate totals
    totals = daily_qs.aggregate(
        total_days=Count("id"),
        new_users=Sum("new_users"),
        active_users_sum=Sum("active_users"),
        total_transactions_success=Sum("total_transactions_success"),
        total_transactions_failed=Sum("total_transactions_failed"),
        total_transactions_refunded=Sum("total_transactions_refunded"),
        total_transferred_amount=Sum("total_transferred_amount"),
        total_refunded_amount=Sum("total_refunded_amount"),
        total_chargeback_amount=Sum("total_chargeback_amount"),
        bill_payments_count=Sum("bill_payments_count"),
        bill_payments_failed=Sum("bill_payments_failed"),
        bill_payments_amount=Sum("bill_payments_amount"),
        fee_revenue=Sum("fee_revenue"),
        bill_commission_revenue=Sum("bill_commission_revenue"),
        fx_spread_revenue=Sum("fx_spread_revenue"),
        net_revenue=Sum("net_revenue"),
        profit=Sum("profit"),
        failed_logins=Sum("failed_logins"),
        incidents=Sum("incidents"),
    )

    # Convert None to 0 for safe calculations
    for key in totals:
        if totals[key] is None:
            totals[key] = 0

    # Calculate ratios
    tx_total = totals["total_transactions_success"] + totals["total_transactions_failed"]
    tx_success_rate = (
        round(totals["total_transactions_success"] / tx_total * 100, 2)
        if tx_total > 0 else 0
    )

    refund_rate = (
        round(totals["total_transactions_refunded"] / totals["total_transactions_success"] * 100, 2)
        if totals["total_transactions_success"] > 0 else 0
    )

    bill_failure_rate = (
        round(totals["bill_payments_failed"] / totals["bill_payments_count"] * 100, 2)
        if totals["bill_payments_count"] > 0 else 0
    )

    # Get latest user count
    latest_metrics = daily_qs.order_by("-date").first()
    total_users = latest_metrics.total_users if latest_metrics else 0

    ratios = {
        "transaction_success_rate_pct": tx_success_rate,
        "refund_rate_pct": refund_rate,
        "bill_payment_failure_rate_pct": bill_failure_rate,
        "avg_daily_active_users": (
            round(totals["active_users_sum"] / totals["total_days"], 1)
            if totals["total_days"] > 0 else 0
        ),
        "total_users_current": total_users,
    }

    # Top countries by users and revenue (latest date)
    latest_date = date_to
    country_qs = CountryUserMetrics.objects.filter(date=latest_date)
    if not country_qs.exists():
        # Try to find the most recent date with data
        latest_country = CountryUserMetrics.objects.order_by("-date").first()
        if latest_country:
            latest_date = latest_country.date
            country_qs = CountryUserMetrics.objects.filter(date=latest_date)

    top_countries = list(
        country_qs.order_by("-net_revenue")[:5].values(
            "country", "count", "active_users", "tx_count", "tx_amount", "net_revenue"
        )
    )

    # Top currencies by volume (latest date)
    currency_qs = CurrencyMetrics.objects.filter(date=latest_date)
    if not currency_qs.exists():
        latest_currency = CurrencyMetrics.objects.order_by("-date").first()
        if latest_currency:
            currency_qs = CurrencyMetrics.objects.filter(date=latest_currency.date)

    top_currencies = list(
        currency_qs.order_by("-tx_amount")[:5].values(
            "currency", "tx_count", "tx_amount", "fx_volume", "fee_revenue", "fx_spread_revenue"
        )
    )

    # Loss days (negative profit)
    loss_days = list(
        daily_qs.filter(profit__lt=0).order_by("profit")[:10].values(
            "date", "profit", "total_transactions_refunded",
            "total_refunded_amount", "total_chargeback_amount", "fee_revenue"
        )
    )

    # Weekly summaries (last 4 weeks)
    weekly_summaries = list(
        WeeklySummary.objects.order_by("-week_start")[:4].values(
            "week_start", "week_end", "new_users", "active_users",
            "total_transactions_success", "net_revenue", "profit"
        )
    )

    # Monthly summaries (last 3 months)
    monthly_summaries = list(
        MonthlySummary.objects.order_by("-month")[:3].values(
            "month", "new_users", "active_users",
            "total_transactions_success", "net_revenue", "profit"
        )
    )

    report = {
        "date_range": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "days_covered": totals["total_days"],
        },
        "totals": {k: _decimal_to_float(v) for k, v in totals.items()},
        "ratios": ratios,
        "top_countries": [
            {k: _decimal_to_float(v) for k, v in c.items()}
            for c in top_countries
        ],
        "top_currencies": [
            {k: _decimal_to_float(v) for k, v in c.items()}
            for c in top_currencies
        ],
        "loss_days": [
            {k: _decimal_to_float(v) for k, v in d.items()}
            for d in loss_days
        ],
        "weekly_summary": [
            {k: _decimal_to_float(v) for k, v in w.items()}
            for w in weekly_summaries
        ],
        "monthly_summary": [
            {k: _decimal_to_float(v) for k, v in m.items()}
            for m in monthly_summaries
        ],
    }

    return report


def generate_business_report_text(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> str:
    """
    Generate a human-readable business report text.

    This is a deterministic report based on metrics data.
    It does NOT include AI-generated content.

    Args:
        date_from: Start date for the report period
        date_to: End date for the report period

    Returns:
        Formatted text report string
    """
    report_json = generate_business_report_json(date_from, date_to)

    # Build the text report
    lines = []
    lines.append("=" * 60)
    lines.append("NEXUS BANK BUSINESS METRICS REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Date range
    dr = report_json["date_range"]
    lines.append(f"Period: {dr['from']} to {dr['to']} ({dr['days_covered']} days)")
    lines.append("")

    # Totals section
    lines.append("--- AGGREGATE TOTALS ---")
    totals = report_json["totals"]
    lines.append(f"Total Users (Current): {report_json['ratios']['total_users_current']}")
    lines.append(f"New Users (Period): {totals['new_users']}")
    lines.append(f"Successful Transactions: {totals['total_transactions_success']}")
    lines.append(f"Failed Transactions: {totals['total_transactions_failed']}")
    lines.append(f"Refunded Transactions: {totals['total_transactions_refunded']}")
    lines.append(f"Total Transferred Amount: {totals['total_transferred_amount']:.2f}")
    lines.append(f"Total Refunded Amount: {totals['total_refunded_amount']:.2f}")
    lines.append(f"Bill Payments Count: {totals['bill_payments_count']}")
    lines.append(f"Bill Payments Failed: {totals['bill_payments_failed']}")
    lines.append(f"Fee Revenue: {totals['fee_revenue']:.2f}")
    lines.append(f"Bill Commission Revenue: {totals['bill_commission_revenue']:.2f}")
    lines.append(f"FX Spread Revenue: {totals['fx_spread_revenue']:.2f}")
    lines.append(f"Net Revenue: {totals['net_revenue']:.2f}")
    lines.append(f"Profit: {totals['profit']:.2f}")
    lines.append(f"Failed Logins: {totals['failed_logins']}")
    lines.append(f"Security Incidents: {totals['incidents']}")
    lines.append("")

    # Ratios section
    lines.append("--- KEY PERFORMANCE INDICATORS ---")
    ratios = report_json["ratios"]
    lines.append(f"Transaction Success Rate: {ratios['transaction_success_rate_pct']}%")
    lines.append(f"Refund Rate: {ratios['refund_rate_pct']}%")
    lines.append(f"Bill Payment Failure Rate: {ratios['bill_payment_failure_rate_pct']}%")
    lines.append(f"Average Daily Active Users: {ratios['avg_daily_active_users']}")
    lines.append("")

    # Top countries
    lines.append("--- TOP COUNTRIES BY REVENUE ---")
    for c in report_json["top_countries"][:3]:
        lines.append(
            f"  {c['country']}: {c['count']} users, {c['active_users']} active, "
            f"{c['tx_count']} tx, revenue {c['net_revenue']:.2f}"
        )
    lines.append("")

    # Top currencies
    lines.append("--- TOP CURRENCIES BY VOLUME ---")
    for c in report_json["top_currencies"][:3]:
        lines.append(
            f"  {c['currency']}: {c['tx_count']} tx, amount {c['tx_amount']:.2f}, "
            f"fee revenue {c['fee_revenue']:.2f}"
        )
    lines.append("")

    # Loss days
    loss_days = report_json["loss_days"]
    if loss_days:
        lines.append("--- LOSS DAYS (Negative Profit) ---")
        for d in loss_days[:5]:
            lines.append(
                f"  {d['date']}: profit {d['profit']:.2f}, "
                f"refunded {d['total_refunded_amount']:.2f}, "
                f"chargeback {d['total_chargeback_amount']:.2f}"
            )
        lines.append(f"  Total loss days in period: {len(loss_days)}")
        lines.append("")

    # Weekly summary
    weekly = report_json["weekly_summary"]
    if weekly:
        lines.append("--- RECENT WEEKLY TRENDS ---")
        for w in weekly[:4]:
            profit_indicator = "+" if w["profit"] >= 0 else ""
            lines.append(
                f"  {w['week_start']} to {w['week_end']}: "
                f"{w['new_users']} new users, {w['total_transactions_success']} tx, "
                f"profit {profit_indicator}{w['profit']:.2f}"
            )
        lines.append("")

    # Monthly summary
    monthly = report_json["monthly_summary"]
    if monthly:
        lines.append("--- MONTHLY SUMMARY ---")
        for m in monthly[:3]:
            profit_indicator = "+" if m["profit"] >= 0 else ""
            lines.append(
                f"  {m['month']}: {m['new_users']} new users, "
                f"{m['total_transactions_success']} tx, "
                f"profit {profit_indicator}{m['profit']:.2f}"
            )
        lines.append("")

    lines.append("=" * 60)
    lines.append("END OF METRICS REPORT")
    lines.append("=" * 60)

    return "\n".join(lines)


def generate_daily_report(target_date: date) -> Dict[str, Any]:
    """
    Generate report for a specific day with context from previous days.

    Args:
        target_date: The specific date to report on

    Returns:
        Dictionary with report_text and report_json
    """
    # Use 30 days of context
    date_from = target_date - timedelta(days=30)
    date_to = target_date

    return {
        "report_text": generate_business_report_text(date_from, date_to),
        "report_json": generate_business_report_json(date_from, date_to),
    }


def generate_monthly_report(month_start: date) -> Dict[str, Any]:
    """
    Generate report for a specific month with context from previous months.

    Args:
        month_start: First day of the target month

    Returns:
        Dictionary with report_text and report_json
    """
    # Calculate month end
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    # Use 90 days of context (includes prior months)
    date_from = month_start - timedelta(days=60)
    date_to = month_end

    return {
        "report_text": generate_business_report_text(date_from, date_to),
        "report_json": generate_business_report_json(date_from, date_to),
    }

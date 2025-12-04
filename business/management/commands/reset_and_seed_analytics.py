import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from business.models import (
    ActiveUserWindow,
    CountryUserMetrics,
    CurrencyMetrics,
    DailyBusinessMetrics,
    MonthlySummary,
    WeeklySummary,
)


class Command(BaseCommand):
    """
    Resets a slice of analytics history and seeds dummy but plausible values
    for demos/visualization.

    Normal operation:
    - Metrics are updated via signals on Transaction/BillPayment/User (see business/signals.py),
      Celery beat tasks (see business/tasks.py), and manual recompute commands
      like `update_metrics`/`backfill_metrics`.

    This command:
    - Deletes analytics rows in the period [2025-01-01, 2025-09-30].
    - Regenerates dummy analytics for [2025-10-01, today] directly into the
      analytics tables (no Celery, no signals), so it is deterministic and
      idempotent. Run it when you need demo-friendly metrics without touching
      core Transaction/BillPayment/User data.
    """

    help = "Reset analytics slice and seed dummy metrics for 2025-10-01 through today."

    DELETE_START = date(2025, 1, 1)
    SEED_START = date(2025, 10, 1)
    DELETE_CUTOFF = date(2025, 10, 1)  # exclusive for deletions

    COUNTRIES = [("Jordan", Decimal("0.6")), ("UAE", Decimal("0.25")),
                 ("KSA", Decimal("0.15"))]
    CURRENCIES = [("JOD", Decimal("0.55")), ("USD", Decimal("0.3")),
                  ("EUR", Decimal("0.15"))]

    def handle(self, *args, **options):
        today = timezone.localdate()
        if today < self.SEED_START:
            self.stderr.write(
                self.style.ERROR(
                    f"Today {today} is before seed start {self.SEED_START}; aborting."
                ))
            return

        seed_end = today

        self.stdout.write(
            f"Resetting analytics between {self.DELETE_START} and {self.DELETE_CUTOFF - timedelta(days=1)}, "
            f"and reseeding {self.SEED_START} to {seed_end}.")

        self._purge_ranges(seed_end)
        self._seed_dummy_data(seed_end)

        self.stdout.write(self.style.SUCCESS("Analytics reset and seed complete."))

    def _purge_ranges(self, seed_end: date):
        """
        Remove historical analytics rows in:
        - [DELETE_START, DELETE_CUTOFF) per requirements
        - [SEED_START, seed_end] to keep idempotent seeding
        """
        delete_lower = self.DELETE_START
        delete_upper = self.DELETE_CUTOFF
        seed_lower = self.SEED_START
        seed_upper = seed_end

        with transaction.atomic():
            DailyBusinessMetrics.objects.filter(
                date__gte=delete_lower, date__lt=delete_upper).delete()
            DailyBusinessMetrics.objects.filter(
                date__gte=seed_lower, date__lte=seed_upper).delete()

            CountryUserMetrics.objects.filter(
                date__gte=delete_lower, date__lt=delete_upper).delete()
            CountryUserMetrics.objects.filter(
                date__gte=seed_lower, date__lte=seed_upper).delete()

            CurrencyMetrics.objects.filter(
                date__gte=delete_lower, date__lt=delete_upper).delete()
            CurrencyMetrics.objects.filter(
                date__gte=seed_lower, date__lte=seed_upper).delete()

            ActiveUserWindow.objects.filter(
                date__gte=delete_lower, date__lt=delete_upper).delete()
            ActiveUserWindow.objects.filter(
                date__gte=seed_lower, date__lte=seed_upper).delete()

            WeeklySummary.objects.filter(
                week_start__gte=delete_lower,
                week_start__lt=delete_upper).delete()
            WeeklySummary.objects.filter(
                week_start__gte=seed_lower,
                week_start__lte=seed_upper).delete()

            MonthlySummary.objects.filter(
                month__gte=delete_lower, month__lt=delete_upper).delete()
            MonthlySummary.objects.filter(
                month__gte=seed_lower, month__lte=seed_upper).delete()

    def _seed_dummy_data(self, seed_end: date):
        rng = random.Random(20251001)
        current_total_users = 1500

        daily_buffer = []
        active_history = []

        day = self.SEED_START
        while day <= seed_end:
            new_users = rng.randint(8, 25)
            churn = rng.randint(0, 3)
            current_total_users = max(
                current_total_users + new_users - churn,
                current_total_users + 1,
            )

            tx_success = rng.randint(30, 180)
            tx_failed = rng.randint(0, max(2, tx_success // 15))
            tx_refund = rng.randint(0, max(1, tx_success // 40))

            avg_amount = self._money(rng.uniform(25, 220))
            total_amount = self._money(Decimal(tx_success) * avg_amount)
            total_refunded = self._money(
                Decimal(tx_refund) * avg_amount * Decimal("0.6"))
            chargeback_amount = self._money(
                Decimal(tx_refund) * avg_amount * Decimal("0.4"))
            fx_volume = self._money(
                total_amount * Decimal(rng.uniform(0.05, 0.2)))

            bill_count = rng.randint(5, 40)
            bill_failed = rng.randint(0, max(1, bill_count // 8))
            bill_amount = self._money(
                Decimal(bill_count) * Decimal(rng.uniform(10, 120)))

            fee_revenue = self._money(total_amount * Decimal("0.008"))
            bill_commission = self._money(bill_amount * Decimal("0.01"))
            fx_spread_revenue = self._money(fx_volume * Decimal("0.003"))
            net_revenue = self._money(fee_revenue + bill_commission +
                                      fx_spread_revenue - total_refunded -
                                      chargeback_amount)
            profit = net_revenue

            base_active = int(tx_success * rng.uniform(1.0, 1.6))
            active_users = min(current_total_users,
                               max(base_active, int(current_total_users *
                                                    0.35)))

            active_history.append(active_users)
            wau = min(current_total_users,
                      int(sum(active_history[-7:]) * 0.6))
            mau = min(current_total_users,
                      int(sum(active_history[-30:]) * 0.5))

            daily = DailyBusinessMetrics(
                date=day,
                new_users=new_users,
                total_users=current_total_users,
                active_users=active_users,
                active_users_7d=wau,
                active_users_30d=mau,
                total_transactions_success=tx_success,
                total_transactions_failed=tx_failed,
                total_transactions_refunded=tx_refund,
                total_transferred_amount=total_amount,
                total_refunded_amount=total_refunded,
                total_chargeback_amount=chargeback_amount,
                avg_transaction_value=avg_amount,
                fx_volume=fx_volume,
                bill_payments_count=bill_count,
                bill_payments_failed=bill_failed,
                bill_payments_amount=bill_amount,
                fee_revenue=fee_revenue,
                bill_commission_revenue=bill_commission,
                fx_spread_revenue=fx_spread_revenue,
                net_revenue=net_revenue,
                profit=profit,
                failed_logins=rng.randint(0, 12),
                incidents=rng.randint(0, 3),
            )
            daily.save()

            self._upsert_active_windows(day, active_users, wau, mau)
            self._seed_country_metrics(day, current_total_users, active_users,
                                       tx_success, total_amount, net_revenue,
                                       rng)
            self._seed_currency_metrics(day, tx_success, total_amount,
                                        fx_volume, fee_revenue,
                                        fx_spread_revenue, rng)

            daily_buffer.append(
                {
                    "date": day,
                    "new_users": new_users,
                    "active_users": active_users,
                    "tx_success": tx_success,
                    "tx_failed": tx_failed,
                    "tx_refund": tx_refund,
                    "total_amount": total_amount,
                    "refunded_amount": total_refunded,
                    "bill_amount": bill_amount,
                    "fee_revenue": fee_revenue,
                    "bill_commission": bill_commission,
                    "fx_spread_revenue": fx_spread_revenue,
                    "net_revenue": net_revenue,
                    "profit": profit,
                })

            day += timedelta(days=1)

        self._seed_weekly(daily_buffer)
        self._seed_monthly(daily_buffer)

    def _upsert_active_windows(self, day, dau, wau, mau):
        ActiveUserWindow.objects.update_or_create(
            date=day, window="dau", defaults={"active_users": dau})
        ActiveUserWindow.objects.update_or_create(
            date=day, window="wau", defaults={"active_users": wau})
        ActiveUserWindow.objects.update_or_create(
            date=day, window="mau", defaults={"active_users": mau})

    def _seed_country_metrics(self, day, total_users, active_users, tx_count,
                              tx_amount, net_revenue, rng):
        for country, share in self.COUNTRIES:
            CountryUserMetrics.objects.create(
                date=day,
                country=country,
                count=int(total_users * share),
                active_users=int(active_users * (share * Decimal("0.9"))),
                tx_count=int(tx_count * share),
                tx_amount=self._money(tx_amount * share),
                net_revenue=self._money(net_revenue * share),
            )

    def _seed_currency_metrics(self, day, tx_count, tx_amount, fx_volume,
                               fee_revenue, fx_spread_revenue, rng):
        for currency, share in self.CURRENCIES:
            CurrencyMetrics.objects.create(
                date=day,
                currency=currency,
                tx_count=int(tx_count * share),
                tx_amount=self._money(tx_amount * share),
                fx_volume=self._money(fx_volume * share),
                fee_revenue=self._money(fee_revenue * share),
                fx_spread_revenue=self._money(fx_spread_revenue * share),
            )

    def _seed_weekly(self, daily_buffer):
        weekly = {}
        for row in daily_buffer:
            week_start = row["date"] - timedelta(days=row["date"].weekday())
            agg = weekly.setdefault(
                week_start, {
                    "new_users": 0,
                    "active_users": 0,
                    "tx_success": 0,
                    "tx_failed": 0,
                    "tx_refund": 0,
                    "total_amount": Decimal("0.00"),
                    "refunded_amount": Decimal("0.00"),
                    "bill_amount": Decimal("0.00"),
                    "fee_revenue": Decimal("0.00"),
                    "bill_commission": Decimal("0.00"),
                    "fx_spread_revenue": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"),
                    "profit": Decimal("0.00"),
                })
            agg["new_users"] += row["new_users"]
            agg["active_users"] += row["active_users"]
            agg["tx_success"] += row["tx_success"]
            agg["tx_failed"] += row["tx_failed"]
            agg["tx_refund"] += row["tx_refund"]
            agg["total_amount"] += row["total_amount"]
            agg["refunded_amount"] += row["refunded_amount"]
            agg["bill_amount"] += row["bill_amount"]
            agg["fee_revenue"] += row["fee_revenue"]
            agg["bill_commission"] += row["bill_commission"]
            agg["fx_spread_revenue"] += row["fx_spread_revenue"]
            agg["net_revenue"] += row["net_revenue"]
            agg["profit"] += row["profit"]

        for week_start, agg in weekly.items():
            week_end = week_start + timedelta(days=6)
            WeeklySummary.objects.update_or_create(
                week_start=week_start,
                defaults={
                    "week_end":
                    week_end,
                    "new_users":
                    agg["new_users"],
                    "active_users":
                    agg["active_users"],
                    "total_transactions_success":
                    agg["tx_success"],
                    "total_transactions_failed":
                    agg["tx_failed"],
                    "total_transactions_refunded":
                    agg["tx_refund"],
                    "total_transferred_amount":
                    self._money(agg["total_amount"]),
                    "total_refunded_amount":
                    self._money(agg["refunded_amount"]),
                    "bill_payments_amount":
                    self._money(agg["bill_amount"]),
                    "fee_revenue":
                    self._money(agg["fee_revenue"]),
                    "bill_commission_revenue":
                    self._money(agg["bill_commission"]),
                    "fx_spread_revenue":
                    self._money(agg["fx_spread_revenue"]),
                    "net_revenue":
                    self._money(agg["net_revenue"]),
                    "profit":
                    self._money(agg["profit"]),
                })

    def _seed_monthly(self, daily_buffer):
        monthly = {}
        for row in daily_buffer:
            month_start = row["date"].replace(day=1)
            agg = monthly.setdefault(
                month_start, {
                    "new_users": 0,
                    "active_users": 0,
                    "tx_success": 0,
                    "tx_failed": 0,
                    "tx_refund": 0,
                    "total_amount": Decimal("0.00"),
                    "refunded_amount": Decimal("0.00"),
                    "bill_amount": Decimal("0.00"),
                    "fee_revenue": Decimal("0.00"),
                    "bill_commission": Decimal("0.00"),
                    "fx_spread_revenue": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"),
                    "profit": Decimal("0.00"),
                })
            agg["new_users"] += row["new_users"]
            agg["active_users"] += row["active_users"]
            agg["tx_success"] += row["tx_success"]
            agg["tx_failed"] += row["tx_failed"]
            agg["tx_refund"] += row["tx_refund"]
            agg["total_amount"] += row["total_amount"]
            agg["refunded_amount"] += row["refunded_amount"]
            agg["bill_amount"] += row["bill_amount"]
            agg["fee_revenue"] += row["fee_revenue"]
            agg["bill_commission"] += row["bill_commission"]
            agg["fx_spread_revenue"] += row["fx_spread_revenue"]
            agg["net_revenue"] += row["net_revenue"]
            agg["profit"] += row["profit"]

        for month_start, agg in monthly.items():
            MonthlySummary.objects.update_or_create(
                month=month_start,
                defaults={
                    "new_users": agg["new_users"],
                    "active_users": agg["active_users"],
                    "total_transactions_success": agg["tx_success"],
                    "total_transactions_failed": agg["tx_failed"],
                    "total_transactions_refunded": agg["tx_refund"],
                    "total_transferred_amount": self._money(agg["total_amount"]),
                    "total_refunded_amount": self._money(agg["refunded_amount"]),
                    "bill_payments_amount": self._money(agg["bill_amount"]),
                    "fee_revenue": self._money(agg["fee_revenue"]),
                    "bill_commission_revenue": self._money(agg["bill_commission"]),
                    "fx_spread_revenue": self._money(agg["fx_spread_revenue"]),
                    "net_revenue": self._money(agg["net_revenue"]),
                    "profit": self._money(agg["profit"]),
                })

    @staticmethod
    def _money(val: Decimal) -> Decimal:
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

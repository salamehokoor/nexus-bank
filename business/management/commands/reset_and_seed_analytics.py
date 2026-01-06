import random
import uuid
from datetime import date, datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum

from api.models import User, Account, Transaction, Biller, BillPayment
from business.models import (
    ActiveUserWindow,
    CountryUserMetrics,
    CurrencyMetrics,
    DailyBusinessMetrics,
    MonthlySummary,
    WeeklySummary,
)

class Command(BaseCommand):
    help = "Reset analytics and seed REAL transaction history/metrics (Jan 2026 - 7 days)."

    # REDUCED: Date range shortened to just 7 days for minimal data and fast loading
    START_DATE = date(2026, 1, 1)
    END_DATE = date(2026, 1, 7)
    
    # Target Biller Account (Requested by User)
    BILLER_TARGET_ACCOUNTS = [
        "525396690794", # Primary
        "525396690795",
        "525396690796",
        "525396690797"
    ]
    
    BILLER_DATA = [
        {"name": "Electricity Co", "category": "Electricity", "fixed": 25},
        {"name": "Water Authority", "category": "Water", "fixed": 12},
        {"name": "Fast Internet", "category": "Internet", "fixed": 30},
        {"name": "Mobile Provider", "category": "Telecom", "fixed": 15},
    ]

    COUNTRIES = [("Jordan", Decimal("0.6")), ("UAE", Decimal("0.25")), ("KSA", Decimal("0.15"))]
    CURRENCIES = [("JOD", Decimal("0.7")), ("USD", Decimal("0.2")), ("EUR", Decimal("0.1"))]
    
    # Track active users history for rolling windows
    active_users_history = []

    def _money(self, val):
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def handle(self, *args, **options):
        self.stdout.write("Initializing Seeding Process...")

        # 1. Accounts Check
        accounts = list(Account.objects.filter(is_active=True).all())
        if not accounts:
            try:
                # Try to fetch all if is_active failed (fallback)
                accounts = list(Account.objects.all())
            except:
                pass
        
        if not accounts:
            self.stdout.write(self.style.ERROR("No active accounts found! Create users first."))
            return
        
        self.stdout.write(f"Found {len(accounts)} accounts to simulate.")

        # 2. Setup Billers
        billers = self.setup_billers()
        
        # 3. Clean
        self.stdout.write("Cleaning old data in range...")
        # Clean Business Metrics
        DailyBusinessMetrics.objects.filter(date__lte=self.END_DATE, date__gte=self.START_DATE).delete()
        CountryUserMetrics.objects.filter(date__lte=self.END_DATE, date__gte=self.START_DATE).delete()
        CurrencyMetrics.objects.filter(date__lte=self.END_DATE, date__gte=self.START_DATE).delete()
        ActiveUserWindow.objects.filter(date__lte=self.END_DATE, date__gte=self.START_DATE).delete()
        # Clean Transactions (Only those created by seeding in this range, actually all in range to match)
        Transaction.objects.filter(created_at__date__gte=self.START_DATE, created_at__date__lte=self.END_DATE).delete()
        BillPayment.objects.filter(created_at__date__gte=self.START_DATE, created_at__date__lte=self.END_DATE).delete()

        # 4. Generate
        daily_buffer = []
        current_date = self.START_DATE
        total_days = (self.END_DATE - self.START_DATE).days + 1
        
        # Reset active users history for rolling windows
        self.active_users_history = []
        
        self.stdout.write(f"Generating data for {total_days} days (Optimized Volume Mode)...")

        processed_count = 0
        while current_date <= self.END_DATE:
            day_stats = self.process_day(current_date, accounts, billers)
            daily_buffer.append(day_stats)
            
            # Track for rolling windows
            self.active_users_history.append({
                "date": current_date,
                "active_users": day_stats["active_users"]
            })
            
            current_date += timedelta(days=1)
            processed_count += 1
            if processed_count % 30 == 0:
                 self.stdout.write(f" ... Processed {processed_count}/{total_days} days")

        # 5. Seed ActiveUserWindow with proper rolling calculations
        self.stdout.write("Seeding ActiveUserWindow (DAU/WAU/MAU)...")
        self._seed_active_windows()
        
        # 6. Summaries
        self._seed_weekly(daily_buffer)
        self._seed_monthly(daily_buffer)
        
        self.stdout.write(self.style.SUCCESS("Seeding Complete."))

    def setup_billers(self):
        billers = []
        # Fallback user for system accounts
        sys_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        
        for idx, b_data in enumerate(self.BILLER_DATA):
            # Resolve account
            acc_num = self.BILLER_TARGET_ACCOUNTS[idx]
            sys_acc, _ = Account.objects.get_or_create(
                account_number=acc_num,
                defaults={
                    "user": sys_user,
                    "type": Account.AccountTypes.BASIC,
                    "balance": Decimal("500000.00"),
                    "currency": "JOD"
                }
            )
            
            biller, _ = Biller.objects.update_or_create(
                name=b_data["name"],
                defaults={
                    "category": b_data["category"],
                    "fixed_amount": Decimal(b_data["fixed"]),
                    "system_account": sys_acc,
                    "description": f"Seeded {b_data['name']}"
                }
            )
            billers.append(biller)
            
        return billers

    def get_random_timestamp(self, day):
        start_ts = datetime.combine(day, time(0, 0, 0))
        # Random time 00:00 to 23:59
        seconds = random.randint(0, 86399)
        dt = start_ts + timedelta(seconds=seconds)
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt

    def process_day(self, day, accounts, billers):
        transactions = []
        bill_payments = []
        
        # REDUCED: 1-3 transactions per ACCOUNT (was 10-20) to minimize lag
        tx_per_account_min = 1
        tx_per_account_max = 3
        
        daily_tx_count = 0
        daily_tx_amount = Decimal("0.00")
        
        active_users_set = set()
        
        # Generated Transactions
        for sender in accounts:
            num = random.randint(tx_per_account_min, tx_per_account_max)
            for _ in range(num):
                receiver = random.choice(accounts)
                if receiver == sender: continue
                
                amount = Decimal(random.randint(10, 500)) # Random value 10-500
                
                created_at = self.get_random_timestamp(day)
                
                t = Transaction(
                    sender_account=sender,
                    receiver_account=receiver,
                    amount=amount,
                    status=Transaction.Status.SUCCESS,
                    sender_balance_after=sender.balance, # Mock
                    receiver_balance_after=receiver.balance # Mock
                )
                t.created_at = created_at # Manually set for bulk_create
                transactions.append(t)
                
                daily_tx_count += 1
                daily_tx_amount += amount
                active_users_set.add(sender.user.id)

        # Generated Bill Payments (Smaller volume)
        for sender in accounts:
             if random.random() < 0.3: # 30% chance to pay bill
                 biller = random.choice(billers)
                 amount = biller.fixed_amount
                 created_at = self.get_random_timestamp(day)
                 
                 bp = BillPayment(
                     user=sender.user,
                     account=sender,
                     biller=biller,
                     reference_number=f"BLK-{day.strftime('%y%m%d')}-{sender.account_number[-4:]}-{random.randint(1000,9999)}",
                     amount=amount,
                     currency=sender.currency,
                     status='PAID',
                 )
                 bp.created_at = created_at
                 bill_payments.append(bp)
                 
                 # Corresponding Transaction for Bill
                 t = Transaction(
                     sender_account=sender,
                     receiver_account=biller.system_account,
                     amount=amount,
                     status=Transaction.Status.SUCCESS,
                     sender_balance_after=sender.balance,
                     receiver_balance_after=biller.system_account.balance 
                 )
                 t.created_at = created_at
                 transactions.append(t)
                 
                 daily_tx_count += 1
                 daily_tx_amount += amount
                 active_users_set.add(sender.user.id)

        # Bulk Create
        if transactions:
            Transaction.objects.bulk_create(transactions, batch_size=1000)
        if bill_payments:
            BillPayment.objects.bulk_create(bill_payments, batch_size=1000)
            
        # FX Volume Calculation (15-25% of transactions are cross-currency)
        fx_percentage = Decimal(str(random.uniform(0.15, 0.25)))
        fx_volume = self._money(daily_tx_amount * fx_percentage)
        fx_spread_revenue = self._money(fx_volume * Decimal("0.003"))  # 0.3% spread
        
        # Fee revenue (0.5% of all transactions)
        fee_revenue = self._money(daily_tx_amount * Decimal("0.005"))
        
        # Bill commission (1% of bill payments)
        bill_amount_total = sum(b.amount for b in bill_payments)
        bill_commission = self._money(bill_amount_total * Decimal("0.01"))
        
        # Total revenue
        total_rev = fee_revenue + fx_spread_revenue + bill_commission
        
        # Metrics
        metrics = DailyBusinessMetrics(
            date=day,
            new_users=random.randint(0, 5),
            total_users=len(accounts), # approx
            active_users=len(active_users_set),
            total_transactions_success=daily_tx_count,
            total_transferred_amount=daily_tx_amount,
            net_revenue=total_rev,
            profit=self._money(total_rev * Decimal("0.8")),
            # Active users (will be updated by rolling window calc)
            active_users_7d=len(active_users_set),
            active_users_30d=len(active_users_set),
            total_transactions_failed=random.randint(0, 3),
            total_transactions_refunded=random.randint(0, 2),
            total_refunded_amount=self._money(Decimal(random.randint(0, 50))),
            total_chargeback_amount=self._money(Decimal(random.randint(0, 20))),
            avg_transaction_value=self._money(daily_tx_amount / daily_tx_count) if daily_tx_count else Decimal(0),
            fx_volume=fx_volume,
            bill_payments_count=len(bill_payments),
            bill_payments_failed=0,
            bill_payments_amount=bill_amount_total,
            fee_revenue=fee_revenue,
            bill_commission_revenue=bill_commission,
            fx_spread_revenue=fx_spread_revenue,
            failed_logins=random.randint(0, 5),
            incidents=random.randint(0, 2)
        )
        metrics.save()
        
        # Mock Metric Breakdowns
        self._seed_country_metrics(day, len(accounts), len(active_users_set), daily_tx_count, daily_tx_amount, total_rev)
        self._seed_currency_metrics(day, daily_tx_count, daily_tx_amount, fx_volume, fx_spread_revenue)

        # Return for aggregator
        return {
            "date": day,
            "tx_success": daily_tx_count,
            "total_amount": daily_tx_amount,
            "active_users": len(active_users_set),
            "new_users": random.randint(0, 5), 
            "tx_failed": random.randint(0, 3), 
            "tx_refund": random.randint(0, 2), 
            "refunded_amount": Decimal(random.randint(0, 50)),
            "bill_amount": bill_amount_total,
            "bill_commission": bill_commission, 
            "fx_spread_revenue": fx_spread_revenue,
            "fee_revenue": fee_revenue, 
            "net_revenue": total_rev,
            "profit": self._money(total_rev * Decimal("0.8")),
            "fx_volume": fx_volume
        }

    def _seed_country_metrics(self, day, total_users, active_users, tx_count, tx_amount, net_revenue):
        remaining_users = total_users
        remaining_active = active_users
        remaining_tx = tx_count
        remaining_amount = tx_amount
        remaining_rev = net_revenue
        
        for idx, (country, share) in enumerate(self.COUNTRIES):
            is_last = (idx == len(self.COUNTRIES) - 1)
            
            if is_last:
                c_users = remaining_users
                c_active = remaining_active
                c_tx = remaining_tx
                c_amount = remaining_amount
                c_rev = remaining_rev
            else:
                c_users = int(total_users * share)
                c_active = int(active_users * share)
                c_tx = int(tx_count * share)
                c_amount = self._money(tx_amount * share)
                c_rev = self._money(net_revenue * share)
            
            # Prevent negative
            c_users = max(0, c_users)
            
            remaining_users -= c_users
            remaining_active -= c_active
            remaining_tx -= c_tx
            remaining_amount -= c_amount
            remaining_rev -= c_rev
            
            CountryUserMetrics.objects.create(
                date=day,
                country=country,
                count=c_users,
                active_users=c_active,
                tx_count=c_tx,
                tx_amount=c_amount,
                net_revenue=c_rev
            )
    
    def _seed_currency_metrics(self, day, tx_count, tx_amount, fx_volume, fx_spread_revenue):
        # Distribute amounts across currencies
        remaining_tx = tx_count
        remaining_amount = tx_amount
        remaining_fx = fx_volume
        remaining_fx_rev = fx_spread_revenue
        
        for idx, (curr, share) in enumerate(self.CURRENCIES):
            is_last = (idx == len(self.CURRENCIES) - 1)
            
            if is_last:
                c_tx = remaining_tx
                c_amount = remaining_amount
                c_fx = remaining_fx
                c_fx_rev = remaining_fx_rev
            else:
                c_tx = int(tx_count * share)
                c_amount = self._money(tx_amount * share)
                c_fx = self._money(fx_volume * share)
                c_fx_rev = self._money(fx_spread_revenue * share)
            
            remaining_tx -= c_tx
            remaining_amount -= c_amount
            remaining_fx -= c_fx
            remaining_fx_rev -= c_fx_rev
            
            CurrencyMetrics.objects.create(
                date=day,
                currency=curr,
                tx_count=c_tx,
                tx_amount=c_amount,
                fx_volume=c_fx,
                fee_revenue=self._money(c_amount * Decimal("0.005")),
                fx_spread_revenue=c_fx_rev
            )
    
    def _seed_active_windows(self):
        """Seed ActiveUserWindow with proper rolling DAU/WAU/MAU calculations."""
        for idx, day_data in enumerate(self.active_users_history):
            day = day_data["date"]
            dau = day_data["active_users"]
            
            # WAU: Sum of last 7 days (unique approximation = avg * 0.7)
            last_7 = self.active_users_history[max(0, idx-6):idx+1]
            wau_sum = sum(d["active_users"] for d in last_7)
            wau = int(wau_sum * 0.6)  # Approx unique users over week
            
            # MAU: Sum of last 30 days (unique approximation = avg * 0.5)
            last_30 = self.active_users_history[max(0, idx-29):idx+1]
            mau_sum = sum(d["active_users"] for d in last_30)
            mau = int(mau_sum * 0.5)  # Approx unique users over month
            
            # Create ActiveUserWindow entries
            ActiveUserWindow.objects.update_or_create(
                date=day, window="dau",
                defaults={"active_users": dau}
            )
            ActiveUserWindow.objects.update_or_create(
                date=day, window="wau",
                defaults={"active_users": wau}
            )
            ActiveUserWindow.objects.update_or_create(
                date=day, window="mau",
                defaults={"active_users": mau}
            )
            
            # Also update DailyBusinessMetrics with accurate WAU/MAU
            DailyBusinessMetrics.objects.filter(date=day).update(
                active_users_7d=wau,
                active_users_30d=mau
            )

    def _seed_weekly(self, daily_buffer):
        weekly = {}
        for row in daily_buffer:
            week_start = row["date"] - timedelta(days=row["date"].weekday())
            agg = weekly.setdefault(
                week_start, {
                    "new_users": 0, "active_users": 0, "tx_success": 0,
                    "total_amount": Decimal("0.00"), "refunded_amount": Decimal("0.00"),
                    "bill_amount": Decimal("0.00"), "fee_revenue": Decimal("0.00"),
                    "bill_commission": Decimal("0.00"), "fx_spread_revenue": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"), "profit": Decimal("0.00"),
                    "tx_failed": 0, "tx_refund": 0
                })
            agg["new_users"] += row["new_users"]
            agg["active_users"] += row["active_users"]
            agg["tx_success"] += row["tx_success"]
            agg["total_amount"] += row["total_amount"]
            agg["bill_amount"] += row["bill_amount"]
            agg["net_revenue"] += row["net_revenue"]
            agg["profit"] += row["profit"]

        for week_start, agg in weekly.items():
            week_end = week_start + timedelta(days=6)
            WeeklySummary.objects.update_or_create(
                week_start=week_start,
                defaults={
                    "week_end": week_end,
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

    def _seed_monthly(self, daily_buffer):
        monthly = {}
        for row in daily_buffer:
            month_start = row["date"].replace(day=1)
            agg = monthly.setdefault(
                month_start, {
                    "new_users": 0, "active_users": 0, "tx_success": 0,
                    "total_amount": Decimal("0.00"), "refunded_amount": Decimal("0.00"),
                    "bill_amount": Decimal("0.00"), "fee_revenue": Decimal("0.00"),
                    "bill_commission": Decimal("0.00"), "fx_spread_revenue": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"), "profit": Decimal("0.00"),
                    "tx_failed": 0, "tx_refund": 0
                })
            # Aggregate
            agg["new_users"] += row["new_users"]
            agg["active_users"] += row["active_users"]
            agg["tx_success"] += row["tx_success"]
            agg["total_amount"] += row["total_amount"]
            agg["bill_amount"] += row["bill_amount"]
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

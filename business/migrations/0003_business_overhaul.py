from decimal import Decimal
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0002_weeklysummary"),
    ]

    operations = [
        # New models
        migrations.CreateModel(
            name="CurrencyMetrics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("currency", models.CharField(max_length=16)),
                ("tx_count", models.IntegerField(default=0)),
                ("tx_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("fx_volume", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("fee_revenue", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("fx_spread_revenue", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
            ],
            options={
                "ordering": ["-date", "currency"],
                "unique_together": {("date", "currency")},
            },
        ),
        migrations.CreateModel(
            name="ActiveUserWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("window", models.CharField(choices=[("dau", "DAU"), ("wau", "WAU"), ("mau", "MAU")], max_length=8)),
                ("active_users", models.IntegerField(default=0)),
            ],
            options={
                "ordering": ["-date"],
                "unique_together": {("date", "window")},
            },
        ),

        # DailyBusinessMetrics alterations
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="active_users_30d",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="active_users_7d",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="bill_commission_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="bill_payments_failed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="fee_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="fx_spread_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="net_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="total_chargeback_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="total_transactions_failed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="total_transactions_refunded",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="total_transactions_success",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="dailybusinessmetrics",
            name="total_refunded_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="dailybusinessmetrics",
            name="avg_transaction_value",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="dailybusinessmetrics",
            name="bill_payments_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="dailybusinessmetrics",
            name="fx_volume",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="dailybusinessmetrics",
            name="profit",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="dailybusinessmetrics",
            name="total_transferred_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.RemoveField(
            model_name="dailybusinessmetrics",
            name="total_transactions",
        ),

        # CountryUserMetrics alterations
        migrations.AddField(
            model_name="countryusermetrics",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="countryusermetrics",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="countryusermetrics",
            name="active_users",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="countryusermetrics",
            name="tx_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="countryusermetrics",
            name="tx_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="countryusermetrics",
            name="net_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),

        # WeeklySummary alterations
        migrations.AddField(
            model_name="weeklysummary",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="active_users",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="total_transactions_failed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="total_transactions_refunded",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="total_transactions_success",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="total_refunded_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="bill_commission_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="fee_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="fx_spread_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="weeklysummary",
            name="net_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="weeklysummary",
            name="bill_payments_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="weeklysummary",
            name="profit",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="weeklysummary",
            name="total_transferred_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.RemoveField(
            model_name="weeklysummary",
            name="total_transactions",
        ),

        # MonthlySummary alterations
        migrations.AddField(
            model_name="monthlysummary",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="active_users",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="total_transactions_failed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="total_transactions_refunded",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="total_transactions_success",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="total_refunded_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="bill_commission_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="fee_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="fx_spread_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="monthlysummary",
            name="net_revenue",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="monthlysummary",
            name="bill_payments_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="monthlysummary",
            name="profit",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AlterField(
            model_name="monthlysummary",
            name="total_transferred_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.RemoveField(
            model_name="monthlysummary",
            name="total_transactions",
        ),

        # Indexes
        migrations.AddIndex(
            model_name="dailybusinessmetrics",
            index=models.Index(fields=["date"], name="business_da_date_0a6f3a_idx"),
        ),
        migrations.AddIndex(
            model_name="dailybusinessmetrics",
            index=models.Index(fields=["-date"], name="business_da__date_63fa8b_idx"),
        ),
        migrations.AddIndex(
            model_name="countryusermetrics",
            index=models.Index(fields=["date"], name="business_co_date_5e1c0b_idx"),
        ),
        migrations.AddIndex(
            model_name="countryusermetrics",
            index=models.Index(fields=["country"], name="business_co_country_3b8698_idx"),
        ),
        migrations.AddIndex(
            model_name="countryusermetrics",
            index=models.Index(fields=["date", "country"], name="business_co_date_co_0b68a4_idx"),
        ),
        migrations.AddIndex(
            model_name="currencymetrics",
            index=models.Index(fields=["date"], name="business_cu_date_9017d0_idx"),
        ),
        migrations.AddIndex(
            model_name="currencymetrics",
            index=models.Index(fields=["currency"], name="business_cu_currency_a438c8_idx"),
        ),
        migrations.AddIndex(
            model_name="currencymetrics",
            index=models.Index(fields=["date", "currency"], name="business_cu_date_cu_1af496_idx"),
        ),
        migrations.AddIndex(
            model_name="weeklysummary",
            index=models.Index(fields=["week_start"], name="business_we_week_st_39e4c0_idx"),
        ),
        migrations.AddIndex(
            model_name="weeklysummary",
            index=models.Index(fields=["-week_start"], name="business_we__week_s_8c4979_idx"),
        ),
        migrations.AddIndex(
            model_name="monthlysummary",
            index=models.Index(fields=["month"], name="business_mo_month_344f3b_idx"),
        ),
        migrations.AddIndex(
            model_name="monthlysummary",
            index=models.Index(fields=["-month"], name="business_mo__month_23287e_idx"),
        ),
    ]

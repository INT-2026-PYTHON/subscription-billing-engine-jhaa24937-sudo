"""
Repositories — the ONLY place SQL lives.

Each repository wraps the Database connection and exposes methods that
take/return domain dataclasses (defined in billing_engine/models/).

⚠️ YOU IMPLEMENT every method body marked TODO.
   The signatures, docstrings, and the LedgerRepository's append-only
   guarantee are already in place — do not change them.

Conventions:
  - Always use parameterized queries (`?` placeholders) — NEVER f-string SQL.
  - Money values are persisted as TEXT using `money.to_storage()`.
  - Dates are persisted as ISO strings (`date.isoformat()`).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from billing_engine.db.database import Database
from billing_engine.money import Money
from billing_engine.models import (
    Customer,
    Plan, PricingType, BillingPeriod,
    Subscription, SubscriptionStatus,
    Invoice, InvoiceStatus, InvoiceLineItem, LineItemKind,
    LedgerEntry, LedgerDirection,
)


# ============================================================
# CUSTOMERS
# ============================================================
class CustomerRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, customer: Customer) -> Customer:
        """Insert and return the customer with `id` populated."""
        # TODO Day 2
        with self.db.transaction() as conn:
            new_id = q.insert_customer(
                conn,
                customer.name,
                customer.email,
                customer.country_code,
                customer.state_code,
            )
        return Customer(
            id=new_id,
            name=customer.name,
            email=customer.email,
            country_code=customer.country_code,
            state_code=customer.state_code,
            created_at=customer.created_at,
        )

    def get(self, customer_id: int) -> Optional[Customer]:
        # TODO Day 2
        with self.db.connect() as conn:
            row = q.select_customer_by_id(conn, customer_id)
        return _customer_from_row(row) if row else None


    def find_by_email(self, email: str) -> Optional[Customer]:
        # TODO Day 2
        with self.db.connect() as conn:
            row = q.select_customer_by_email(conn, email)
        return _customer_from_row(row) if row else None

    def list_all(self) -> list[Customer]:
        # TODO Day 2
        with self.db.connect() as conn:
            rows = q.select_all_customers(conn)
        return [_customer_from_row(row) for row in rows]



# ============================================================
# PLANS  +  PLAN TIERS
# ============================================================
class PlanRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, plan: Plan) -> Plan:
        # TODO Day 2.
        with self.db.transaction() as conn:
            new_id = q.insert_plan(
                conn,
                plan.name,
                plan.pricing_type.value,
                plan.billing_period.value,
                plan.currency,
                plan.config_json,
            )
        return Plan(
            id=new_id,
            name=plan.name,
            pricing_type=plan.pricing_type,
            billing_period=plan.billing_period,
            currency=plan.currency,
            config_json=plan.config_json,
        )


    def get(self, plan_id: int) -> Optional[Plan]:
        # TODO Day 2.
        with self.db.connect() as conn:
            row = q.select_plan_by_id(conn, plan_id)
        return _plan_from_row(row) if row else None

    def list_all(self) -> list[Plan]:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement PlanRepository.list_all")


class PlanTierRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, plan_id: int, from_units: int, to_units: Optional[int], unit_price: Money) -> int:
        """Insert a tier; return new id."""
        # TODO Day 2.
        with self.db.transaction() as conn:
            return q.insert_plan_tier(conn, plan_id, from_units, to_units, unit_price.to_storage())


    def list_for_plan(self, plan_id: int, currency: str) -> list[tuple[int, Optional[int], Money]]:
        """Return [(from_units, to_units, unit_price)] ordered by from_units.

        Currency is passed in (the plan_tiers table stores only the amount;
        currency lives on the parent plan).
        """
        # TODO Day 2.
        with self.db.connect() as conn:
            rows = q.select_plan_tiers(conn, plan_id)
        return [(row[0], row[1], Money(row[2], currency)) for row in rows]


# ============================================================
# DISCOUNTS
# ============================================================
class DiscountRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, code: str, discount_type: str, value: str, currency: Optional[str] = None) -> int:
        # TODO Day 2.
        with self.db.transaction() as conn:
            return q.insert_discount(conn, code, discount_type, value, currency)

    def get_by_code(self, code: str) -> Optional[dict]:
        """Return raw row as dict, or None. (Discount has no dataclass yet — we use a dict for now.)"""
        # TODO Day 2.
        with self.db.connect() as conn:
            row = q.select_discount_by_code(conn, code)
        return dict(row) if row else None


# ============================================================
# SUBSCRIPTIONS
# ============================================================
class SubscriptionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, subscription: Subscription) -> Subscription:
        # TODO Day 2.
        with self.db.transaction() as conn:
            new_id = q.insert_subscription(
                conn,
                subscription.customer_id,
                subscription.plan_id,
                subscription.status.value,
                subscription.current_period_start.isoformat(),
                subscription.current_period_end.isoformat(),
                subscription.trial_end.isoformat() if subscription.trial_end else None,
                subscription.discount_id,
                subscription.past_due_since.isoformat() if subscription.past_due_since else None,
            )
        return Subscription(
            id=new_id,
            customer_id=subscription.customer_id,
            plan_id=subscription.plan_id,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_end=subscription.trial_end,
            discount_id=subscription.discount_id,
            past_due_since=subscription.past_due_since,
        )


    def get(self, subscription_id: int) -> Optional[Subscription]:
        # TODO Day 2.
        with self.db.connect() as conn:
            row = q.select_subscription_by_id(conn, subscription_id)
        return _subscription_from_row(row) if row else None

    def list_all(self) -> list[Subscription]:
        """All subscriptions, regardless of status. Used by BillingCycle trial scan."""
        # TODO Day 2.
        with self.db.connect() as conn:
            rows = q.select_all_subscriptions(conn)
        return [_subscription_from_row(row) for row in rows]

    def get_due_for_billing(self, as_of: date) -> list[Subscription]:
        """Subscriptions whose current_period_end <= as_of AND status is ACTIVE.
        (Hint: trial subscriptions whose trial_end <= as_of should also become billable —
         either handle that here or transition them to ACTIVE first in BillingCycle.)
        """
        # TODO Day 2.
        with self.db.connect() as conn:
            rows = q.select_due_subscriptions(conn, as_of.isoformat())
        return [_subscription_from_row(row) for row in rows]


    def update_period(self, subscription_id: int, new_start: date, new_end: date) -> None:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement SubscriptionRepository.update_period")

    def update_status(
        self,
        subscription_id: int,
        new_status: SubscriptionStatus,
        past_due_since: Optional[date] = None,
    ) -> None:
        # TODO Day 2.
        self,
        subscription_id: int,
        new_status: SubscriptionStatus,
        past_due_since: Optional[date] = None,
    ) -> None:

    def update_plan(self, subscription_id: int, new_plan_id: int) -> None:
        """Switch the subscription to a different plan (used by upgrade flow)."""
        # TODO Day 4.
        raise NotImplementedError("Day 4: implement SubscriptionRepository.update_plan")


# ============================================================
# USAGE
# ============================================================
class UsageRecordRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, subscription_id: int, metric: str, quantity: int) -> int:
        # TODO Day 2.
         with self.db.transaction() as conn:
            return q.insert_usage_record(conn, subscription_id, metric, quantity)


    def sum_for_period(
        self, subscription_id: int, metric: str, period_start: date, period_end: date
    ) -> int:
        # TODO Day 2: SELECT COALESCE(SUM(quantity), 0) ...
        self, subscription_id: int, metric: str, period_start: date, period_end: date
    ) -> int:
        with self.db.connect() as conn:
            return q.sum_usage_for_subscription_metric(conn, subscription_id, metric)



# ============================================================
# INVOICES + LINE ITEMS
# ============================================================
class InvoiceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, invoice: Invoice) -> Invoice:
        """Insert invoice (NOT line items — that's the other repo).

        Must respect the UNIQUE(subscription_id, period_start) constraint.
        If a duplicate is attempted, raise sqlite3.IntegrityError naturally
        (caller is responsible for handling it — this gives idempotency).
        """
        # TODO Day 2.
        with self.db.transaction() as conn:
            new_id = q.insert_invoice(
                conn,
                invoice.subscription_id,
                invoice.period_start.isoformat(),
                invoice.period_end.isoformat(),
                invoice.total.currency,
                invoice.subtotal.to_storage(),
                invoice.discount_total.to_storage(),
                invoice.tax_total.to_storage(),
                invoice.total.to_storage(),
                invoice.status.value,
                invoice.issued_at.isoformat() if invoice.issued_at else None,
                invoice.pdf_path,
            )
        return Invoice(
            id=new_id,
            subscription_id=invoice.subscription_id,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            subtotal=invoice.subtotal,
            discount_total=invoice.discount_total,
            tax_total=invoice.tax_total,
            total=invoice.total,
            status=invoice.status,
            issued_at=invoice.issued_at,
            pdf_path=invoice.pdf_path,
            line_items=invoice.line_items,
        )

    def get(self, invoice_id: int) -> Optional[Invoice]:
        # TODO Day 2.
        with self.db.connect() as conn:
            row = q.select_invoice_by_id(conn, invoice_id)
        return _invoice_from_row(row) if row else None


    def count_for_subscription(self, subscription_id: int) -> int:
        """Used by FirstMonthFree discount."""
        # TODO Day 2.
        

    def mark_paid(self, invoice_id: int) -> None:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement InvoiceRepository.mark_paid")

    def mark_failed(self, invoice_id: int) -> None:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement InvoiceRepository.mark_failed")

    def set_pdf_path(self, invoice_id: int, path: str) -> None:
        # TODO Day 4.
        raise NotImplementedError("Day 4: implement InvoiceRepository.set_pdf_path")


class InvoiceLineItemRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, line_item: InvoiceLineItem) -> InvoiceLineItem:
        # TODO Day 2.
        if line_item.invoice_id is None:
            raise ValueError("line_item.invoice_id is required")
        with self.db.transaction() as conn:
            new_id = q.insert_invoice_line_item(
                conn,
                line_item.invoice_id,
                line_item.description,
                line_item.amount.to_storage(),
                line_item.kind.value,
            )
        return InvoiceLineItem(
            id=new_id,
            invoice_id=line_item.invoice_id,
            description=line_item.description,
            amount=line_item.amount,
            kind=line_item.kind,
        )


    def list_for_invoice(self, invoice_id: int) -> list[InvoiceLineItem]:
        # TODO Day 2.
          with self.db.connect() as conn:
            invoice = q.select_invoice_by_id(conn, invoice_id)
            if invoice is None:
                return []
            rows = q.select_line_items_for_invoice(conn, invoice_id)
        return [_line_item_from_row(row, invoice["currency"]) for row in rows]



# ============================================================
# LEDGER — APPEND-ONLY (do not implement update/delete)
# ============================================================
class LedgerRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement LedgerRepository.add")

    def list_for_customer(self, customer_id: int) -> list[LedgerEntry]:
        # TODO Day 2.
        raise NotImplementedError("Day 2: implement LedgerRepository.list_for_customer")

    # ✅ These two methods are intentionally implemented to REJECT — do not override.
    def update(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")


# ============================================================
# PAYMENT ATTEMPTS
# ============================================================
class PaymentAttemptRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        invoice_id: int,
        attempt_no: int,
        status: str,
        failure_reason: Optional[str],
        next_retry_at: Optional[datetime],
    ) -> int:
        # TODO Day 3.
        raise NotImplementedError("Day 3: implement PaymentAttemptRepository.add")

    def list_for_invoice(self, invoice_id: int) -> list[dict]:
        # TODO Day 3.
        raise NotImplementedError("Day 3: implement PaymentAttemptRepository.list_for_invoice")

    def count_for_invoice(self, invoice_id: int) -> int:
        # TODO Day 3.
        raise NotImplementedError("Day 3: implement PaymentAttemptRepository.count_for_invoice")

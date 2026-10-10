"""Compare sample order and payment CSV files and report exceptions."""

import csv
import html
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
ORDERS_FILE = PROJECT_DIR / "data" / "orders.csv"
PAYMENTS_FILE = PROJECT_DIR / "data" / "payments.csv"
REPORTS_DIR = PROJECT_DIR / "reports"
EXCEPTIONS_FILE = REPORTS_DIR / "exceptions.csv"
SUMMARY_FILE = REPORTS_DIR / "summary.json"
RECONCILIATION_FILE = REPORTS_DIR / "reconciliation.html"

REQUIRED_FIELDS = ("transaction_id", "customer_id", "amount", "currency")


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def money(value):
    try:
        return Decimal(value.strip())
    except (AttributeError, InvalidOperation):
        return None


def add_exception(exceptions, kind, transaction_id="", order_amount="", payment_amount="", details=""):
    exceptions.append(
        {
            "exception_type": kind,
            "transaction_id": transaction_id,
            "order_amount": order_amount,
            "payment_amount": payment_amount,
            "details": details,
        }
    )


def format_inr(value):
    return f"₹{value:,.2f}" if value is not None else "—"


def write_reconciliation_report(orders, payments, order_counts, payment_counts, summary):
    """Create a readable, filterable report with one row per transaction ID."""
    order_groups = {}
    payment_groups = {}
    for row in orders:
        transaction_id = (row.get("transaction_id") or "").strip()
        if transaction_id:
            order_groups.setdefault(transaction_id, []).append(row)
    for row in payments:
        transaction_id = (row.get("transaction_id") or "").strip()
        if transaction_id:
            payment_groups.setdefault(transaction_id, []).append(row)

    ids = sorted(order_groups.keys() | payment_groups.keys())
    report_rows = []
    status_counts = Counter()
    for transaction_id in ids:
        order_rows = order_groups.get(transaction_id, [])
        payment_rows = payment_groups.get(transaction_id, [])
        issues = []
        order_total = sum((money(row.get("amount")) or Decimal("0.00") for row in order_rows), Decimal("0.00"))
        payment_total = sum((money(row.get("amount")) or Decimal("0.00") for row in payment_rows), Decimal("0.00"))

        if order_counts.get(transaction_id, 0) > 1:
            issues.append(f"Duplicate order ID ({order_counts[transaction_id]} rows)")
        if payment_counts.get(transaction_id, 0) > 1:
            issues.append(f"Duplicate payment ID ({payment_counts[transaction_id]} rows)")
        if not order_rows:
            issues.append("Payment has no matching order")
        if not payment_rows:
            issues.append("Order has no matching payment")

        for source_name, rows in (("order", order_rows), ("payment", payment_rows)):
            for row in rows:
                for field in REQUIRED_FIELDS:
                    if not (row.get(field) or "").strip():
                        issue = f"Missing {field} in {source_name}"
                        if issue not in issues:
                            issues.append(issue)

        if len(order_rows) == 1 and len(payment_rows) == 1:
            order = order_rows[0]
            payment = payment_rows[0]
            if order.get("customer_id", "").strip() and payment.get("customer_id", "").strip() and order["customer_id"].strip() != payment["customer_id"].strip():
                issues.append("Customer ID mismatch")
            if order.get("currency", "").strip() and payment.get("currency", "").strip() and order["currency"].strip() != payment["currency"].strip():
                issues.append("Currency mismatch")
            order_amount = money(order.get("amount"))
            payment_amount = money(payment.get("amount"))
            if order_amount is not None and payment_amount is not None and order_amount != payment_amount:
                issues.append("Amount mismatch")

        status = "Matched" if not issues else "Needs review"
        status_counts[status] += 1
        order_display = format_inr(order_total) if order_rows else "—"
        payment_display = format_inr(payment_total) if payment_rows else "—"
        if len(order_rows) > 1:
            order_display += f" ({len(order_rows)} rows)"
        if len(payment_rows) > 1:
            payment_display += f" ({len(payment_rows)} rows)"
        report_rows.append(
            f"<tr data-status='{status.lower().replace(' ', '-')}'><td>{html.escape(transaction_id)}</td>"
            f"<td>{order_display}</td><td>{payment_display}</td>"
            f"<td><span class='badge {'ok' if not issues else 'review'}'>{status}</span></td>"
            f"<td>{html.escape('; '.join(issues) if issues else 'Order and payment agree')}</td></tr>"
        )

    report_html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reconciliation Report</title>
<style>
* {{ box-sizing: border-box; }} body {{ margin: 0; background: #f4f7fb; color: #172033; font: 15px/1.5 Arial, sans-serif; }}
main {{ max-width: 1120px; margin: 36px auto; padding: 0 20px; }} h1 {{ margin-bottom: 4px; font-size: 28px; }}
.sub {{ color: #667085; margin-top: 0; }} .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 24px 0; }}
.card {{ background: white; border: 1px solid #e3e8ef; border-radius: 12px; padding: 16px; }} .label {{ color: #667085; font-size: 13px; }}
.value {{ font-size: 22px; font-weight: 700; margin-top: 4px; }} .toolbar {{ display: flex; gap: 12px; margin: 20px 0 12px; }}
input, select {{ padding: 10px 12px; border: 1px solid #ccd4df; border-radius: 8px; background: #fff; font-size: 14px; }} input {{ flex: 1; }}
.table-wrap {{ overflow-x: auto; background: #fff; border: 1px solid #e3e8ef; border-radius: 12px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 760px; }} th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid #edf0f4; }}
th {{ background: #f8fafc; color: #475467; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }} tr:last-child td {{ border-bottom: 0; }}
.badge {{ display: inline-block; padding: 4px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
.ok {{ background: #dcfce7; color: #166534; }} .review {{ background: #fff1d6; color: #92400e; }}
.note {{ color: #667085; font-size: 13px; margin-top: 14px; }} @media (max-width: 700px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
</style></head><body><main>
<h1>Order and Payment Reconciliation</h1><p class="sub">Review each transaction across the order and payment files.</p>
<section class="cards">
<div class="card"><div class="label">Transactions</div><div class="value">{len(ids)}</div></div>
<div class="card"><div class="label">Matched</div><div class="value">{status_counts['Matched']}</div></div>
<div class="card"><div class="label">Needs review</div><div class="value">{status_counts['Needs review']}</div></div>
<div class="card"><div class="label">Total difference</div><div class="value">₹{summary['total_difference_inr']}</div></div>
</section>
<div class="toolbar"><input id="search" type="search" placeholder="Search transaction ID or issue"><select id="filter"><option value="all">All transactions</option><option value="matched">Matched</option><option value="needs-review">Needs review</option></select></div>
<div class="table-wrap"><table><thead><tr><th>Transaction ID</th><th>Order amount</th><th>Payment amount</th><th>Status</th><th>Check result</th></tr></thead><tbody id="rows">{''.join(report_rows)}</tbody></table></div>
<p class="note">Amounts are shown in INR. Records with duplicate IDs or missing values are flagged for review.</p>
</main><script>
const search=document.getElementById('search'),filter=document.getElementById('filter');
function updateRows(){{const q=search.value.toLowerCase();const f=filter.value;document.querySelectorAll('#rows tr').forEach(r=>{{const matchText=r.innerText.toLowerCase().includes(q);const matchStatus=f==='all'||r.dataset.status===f;r.hidden=!(matchText&&matchStatus);}});}}
search.addEventListener('input',updateRows);filter.addEventListener('change',updateRows);
</script></body></html>'''
    RECONCILIATION_FILE.write_text(report_html, encoding="utf-8")


def main():
    orders = read_csv(ORDERS_FILE)
    payments = read_csv(PAYMENTS_FILE)
    exceptions = []

    for source_name, rows in (("orders", orders), ("payments", payments)):
        for row_number, row in enumerate(rows, start=2):
            for field in REQUIRED_FIELDS:
                if not (row.get(field) or "").strip():
                    add_exception(
                        exceptions,
                        "Missing required field",
                        row.get("transaction_id", ""),
                        details=f"{source_name}.csv row {row_number}: {field} is blank",
                    )
            if (row.get("amount") or "").strip() and money(row["amount"]) is None:
                add_exception(
                    exceptions,
                    "Invalid amount",
                    row.get("transaction_id", ""),
                    details=f"{source_name}.csv row {row_number}: amount is not numeric",
                )

    order_counts = Counter((row.get("transaction_id") or "").strip() for row in orders)
    payment_counts = Counter((row.get("transaction_id") or "").strip() for row in payments)
    order_counts.pop("", None)
    payment_counts.pop("", None)

    for transaction_id, count in order_counts.items():
        if count > 1:
            add_exception(exceptions, "Duplicate order ID", transaction_id, details=f"Found {count} rows in orders.csv")
    for transaction_id, count in payment_counts.items():
        if count > 1:
            add_exception(exceptions, "Duplicate payment ID", transaction_id, details=f"Found {count} rows in payments.csv")

    unique_orders = {
        (row.get("transaction_id") or "").strip(): row
        for row in orders
        if (row.get("transaction_id") or "").strip() and order_counts[(row.get("transaction_id") or "").strip()] == 1
    }
    unique_payments = {
        (row.get("transaction_id") or "").strip(): row
        for row in payments
        if (row.get("transaction_id") or "").strip() and payment_counts[(row.get("transaction_id") or "").strip()] == 1
    }

    for transaction_id in sorted(order_counts.keys() - payment_counts.keys()):
        add_exception(exceptions, "Order has no payment", transaction_id, order_amount=unique_orders[transaction_id].get("amount", ""))
    for transaction_id in sorted(payment_counts.keys() - order_counts.keys()):
        add_exception(exceptions, "Payment has no order", transaction_id, payment_amount=unique_payments[transaction_id].get("amount", ""))

    comparable_ids = order_counts.keys() & payment_counts.keys()
    for transaction_id in sorted(comparable_ids):
        if order_counts[transaction_id] != 1 or payment_counts[transaction_id] != 1:
            continue
        order_amount = money(unique_orders[transaction_id].get("amount"))
        payment_amount = money(unique_payments[transaction_id].get("amount"))
        if order_amount is not None and payment_amount is not None and order_amount != payment_amount:
            add_exception(
                exceptions,
                "Amount mismatch",
                transaction_id,
                str(order_amount),
                str(payment_amount),
                f"Difference: {order_amount - payment_amount:.2f} INR",
            )

    def valid_total(rows):
        return sum((amount for row in rows if (amount := money(row.get("amount"))) is not None), Decimal("0.00"))

    order_total = valid_total(orders)
    payment_total = valid_total(payments)
    type_counts = Counter(item["exception_type"] for item in exceptions)
    summary = {
        "orders_rows": len(orders),
        "payments_rows": len(payments),
        "orders_total_inr": f"{order_total:.2f}",
        "payments_total_inr": f"{payment_total:.2f}",
        "total_difference_inr": f"{order_total - payment_total:.2f}",
        "exception_count": len(exceptions),
        "exception_counts_by_type": dict(sorted(type_counts.items())),
    }

    REPORTS_DIR.mkdir(exist_ok=True)
    with EXCEPTIONS_FILE.open("w", newline="", encoding="utf-8") as file:
        columns = ("exception_type", "transaction_id", "order_amount", "payment_amount", "details")
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(exceptions)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_reconciliation_report(orders, payments, order_counts, payment_counts, summary)

    print("Data Quality and Reconciliation Workbench")
    print(f"Order rows:          {summary['orders_rows']}")
    print(f"Payment rows:        {summary['payments_rows']}")
    print(f"Order total:         INR {summary['orders_total_inr']}")
    print(f"Payment total:       INR {summary['payments_total_inr']}")
    print(f"Total difference:    INR {summary['total_difference_inr']}")
    print(f"Exceptions found:    {summary['exception_count']}")
    print(f"Reports saved in:    {REPORTS_DIR.relative_to(PROJECT_DIR)}")
    print(f"Open this report:    {RECONCILIATION_FILE.name}")


if __name__ == "__main__":
    main()

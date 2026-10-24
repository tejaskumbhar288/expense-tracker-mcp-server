from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, select, update

from db import expenses, get_engine

IST = ZoneInfo("Asia/Kolkata")
CATEGORIES = (
    "food",
    "transport",
    "shopping",
    "bills",
    "health",
    "entertainment",
    "rent",
    "investment",
    "ai",
    "other",
)

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",  # year first
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",  # day first (Indian convention)
    "%d %b %Y",
    "%d %B %Y",  # 26 Oct 2026, 26 October 2026
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",  # Oct 26, 2026
    "%m/%d/%Y",
    "%m-%d-%Y",  # month first, last resort
)


def today() -> date:
    return datetime.now(IST).date()


def parse_date(value: str) -> date:
    text = " ".join(value.strip().split())
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Could not understand the date '{value}'. "
        "Try formats like 2026-10-26, 26/10/2026 or 26 Oct 2026."
    )


def _check_not_future(d: date) -> None:
    if d > today():
        raise ValueError("Date cannot be in the future.")


def _to_paise(amount: float) -> int:
    paise = round(amount * 100)
    if paise <= 0:
        raise ValueError("Amount must be greater than zero.")
    return paise


def _clean_category(category: str) -> str:
    c = category.strip().lower()
    if c not in CATEGORIES:
        raise ValueError(
            f"Unknown category '{category}'. Use one of: {', '.join(CATEGORIES)}."
        )
    return c


def _row(r) -> dict:
    return {
        "id": r.id,
        "amount": r.amount_paise / 100,
        "category": r.category,
        "description": r.description,
        "spent_on_date": r.spent_on_date.isoformat(),
    }


def add_expense(
    amount: float,
    category: str,
    description: str = "",
    spent_on_date: date | None = None,
) -> dict:
    spent_on_date = spent_on_date or today()
    _check_not_future(spent_on_date)

    values = {
        "amount_paise": _to_paise(amount),
        "category": _clean_category(category),
        "description": description.strip()[:200],
        "spent_on_date": spent_on_date,
    }
    with get_engine().begin() as conn:
        new_id = conn.execute(insert(expenses).values(**values)).inserted_primary_key[0]

    return {
        "id": new_id,
        "amount": values["amount_paise"] / 100,
        "category": values["category"],
        "description": values["description"],
        "spent_on_date": spent_on_date.isoformat(),
    }


def list_expenses(
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if start and end and start > end:
        raise ValueError("start_date must not be after end_date.")

    q = (
        select(expenses)
        .order_by(expenses.c.spent_on_date.desc(), expenses.c.id.desc())
        .limit(max(1, min(limit, 200)))
    )
    if start:
        q = q.where(expenses.c.spent_on_date >= start)
    if end:
        q = q.where(expenses.c.spent_on_date <= end)
    if category:
        q = q.where(expenses.c.category == _clean_category(category))

    with get_engine().connect() as conn:
        return [_row(r) for r in conn.execute(q)]


def get_summary(start: date | None = None, end: date | None = None) -> dict:
    if start and end and start > end:
        raise ValueError("start_date must not be after end_date.")

    q = (
        select(
            expenses.c.category,
            func.sum(expenses.c.amount_paise).label("total_paise"),
            func.count().label("n"),
        )
        .group_by(expenses.c.category)
        .order_by(func.sum(expenses.c.amount_paise).desc())
    )
    if start:
        q = q.where(expenses.c.spent_on_date >= start)
    if end:
        q = q.where(expenses.c.spent_on_date <= end)

    with get_engine().connect() as conn:
        rows = conn.execute(q).all()

    return {
        "total": sum(r.total_paise for r in rows) / 100,
        "count": sum(r.n for r in rows),
        "by_category": {r.category: r.total_paise / 100 for r in rows},
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
    }


def update_expense(
    expense_id: int,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    spent_on_date: date | None = None,
) -> dict:
    # Empty or missing values mean "leave this field alone". Validate everything
    # BEFORE touching the database, so a bad input never half-updates a row.
    changes: dict = {}
    if amount is not None:
        changes["amount_paise"] = _to_paise(amount)
    if category is not None and category.strip():
        changes["category"] = _clean_category(category)
    if description is not None and description.strip():
        changes["description"] = description.strip()[:200]
    if spent_on_date is not None:
        _check_not_future(spent_on_date)
        changes["spent_on_date"] = spent_on_date

    if not changes:
        raise ValueError(
            "Nothing to update. Provide at least one of: "
            "amount, category, description, spent_on_date."
        )

    with get_engine().begin() as conn:
        before = conn.execute(
            select(expenses).where(expenses.c.id == expense_id)
        ).first()
        if before is None:
            raise ValueError(f"No expense with id {expense_id}.")
        conn.execute(
            update(expenses).where(expenses.c.id == expense_id).values(**changes)
        )
        after = conn.execute(
            select(expenses).where(expenses.c.id == expense_id)
        ).first()

    return {"before": _row(before), "after": _row(after)}


def delete_expense(expense_id: int) -> dict:
    with get_engine().begin() as conn:
        row = conn.execute(select(expenses).where(expenses.c.id == expense_id)).first()
        if row is None:
            raise ValueError(f"No expense with id {expense_id}.")
        conn.execute(delete(expenses).where(expenses.c.id == expense_id))
    return _row(row)

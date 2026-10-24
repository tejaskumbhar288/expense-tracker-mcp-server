from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

import service

mcp = FastMCP(
    name="Expense Tracker",
    instructions="Log and analyse personal expenses in INR (rupees).",
)


@mcp.tool
def ping() -> str:
    """Health check. Returns 'pong'."""
    return "pong"


@mcp.tool(annotations={"destructiveHint": False})
def add_expense(
    amount: float,
    category: str,
    description: str = "",
    spent_on_date: str | None = None,
) -> dict:
    """Record one expense. amount is in rupees. category must be one of:
    food, transport, shopping, bills, health, entertainment, rent, investment,
    ai, other. Use ai for AI subscriptions, API credits and AI tools.
    spent_on_date is a date such as 2026-10-20, 20/10/2026 or 20 Oct 2026
    (day comes first in slash dates); it defaults to today."""
    try:
        parsed = service.parse_date(spent_on_date) if spent_on_date else None
        return service.add_expense(amount, category, description, parsed)
    except ValueError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations={"readOnlyHint": True})
def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> dict:
    """List expenses, newest first. Optional filters: start_date and end_date
    (inclusive; formats like 2026-10-01 or 01/10/2026), and category (one of
    food, transport, shopping, bills, health, entertainment, rent, investment, ai, other). 
    limit defaults to 50 and is capped at 200."""
    try:
        start = service.parse_date(start_date) if start_date else None
        end = service.parse_date(end_date) if end_date else None
        rows = service.list_expenses(start, end, category, limit)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return {"count": len(rows), "expenses": rows}


@mcp.tool(annotations={"readOnlyHint": True})
def get_summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Total spending in rupees, the number of expenses, and a per-category
    breakdown (largest first). Optional start_date and end_date (inclusive;
    formats like 2026-10-01 or 01/10/2026). With no dates it covers all expenses."""
    try:
        start = service.parse_date(start_date) if start_date else None
        end = service.parse_date(end_date) if end_date else None
        return service.get_summary(start, end)
    except ValueError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True})
def update_expense(
    expense_id: int,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    spent_on_date: str | None = None,
) -> dict:
    """Change one or more fields of an existing expense. expense_id comes from
    list_expenses. Provide ONLY the fields that should change; omitted fields
    stay as they are. amount is in rupees. category is one of: food, transport, 
    shopping, bills, health, entertainment, rent, investment, ai, other.
    spent_on_date accepts formats like 2026-10-20 or 20/10/2026.
    Returns the record before and after the change."""
    try:
        parsed = service.parse_date(spent_on_date) if spent_on_date else None
        return service.update_expense(expense_id, amount, category, description, parsed)
    except ValueError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations={"destructiveHint": True})
def delete_expense(expense_id: int) -> dict:
    """Permanently delete one expense by its id (ids come from list_expenses).
    This cannot be undone. Returns the deleted record."""
    try:
        return service.delete_expense(expense_id)
    except ValueError as e:
        raise ToolError(str(e)) from e


if __name__ == "__main__":
    mcp.run()

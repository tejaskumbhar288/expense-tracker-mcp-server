import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp

ALL_TOOLS = {
    "ping",
    "add_expense",
    "list_expenses",
    "get_summary",
    "update_expense",
    "delete_expense",
}


async def test_all_tools_are_registered():
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert ALL_TOOLS <= names


async def test_safety_hints_are_set():
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert tools["delete_expense"].annotations.destructiveHint is True
    assert tools["list_expenses"].annotations.readOnlyHint is True
    assert tools["get_summary"].annotations.readOnlyHint is True


async def test_full_flow():
    async with Client(mcp) as client:
        added = await client.call_tool(
            "add_expense",
            {
                "amount": 450,
                "category": "food",
                "description": "lunch",
                "spent_on_date": "20/10/2026",
            },
        )
        assert added.data["spent_on_date"] == "2026-10-20"  # normalised output
        expense_id = added.data["id"]

        updated = await client.call_tool(
            "update_expense", {"expense_id": expense_id, "amount": 350}
        )
        assert updated.data["before"]["amount"] == 450
        assert updated.data["after"]["amount"] == 350

        summary = await client.call_tool("get_summary", {})
        assert summary.data["total"] == 350

        await client.call_tool("delete_expense", {"expense_id": expense_id})
        listed = await client.call_tool("list_expenses", {})
        assert listed.data["count"] == 0


@pytest.mark.parametrize(
    "tool, args, message",
    [
        ("add_expense", {"amount": 10, "category": "pizza"}, "Unknown category"),
        ("add_expense", {"amount": -5, "category": "food"}, "greater than zero"),
        (
            "add_expense",
            {"amount": 10, "category": "food", "spent_on_date": "banana"},
            "Could not understand",
        ),
        (
            "add_expense",
            {"amount": 10, "category": "food", "spent_on_date": "2099-01-01"},
            "future",
        ),
        ("update_expense", {"expense_id": 1}, "Nothing to update"),
        ("update_expense", {"expense_id": 999, "amount": 5}, "No expense"),
        ("delete_expense", {"expense_id": 999}, "No expense"),
    ],
)
async def test_errors_are_readable(tool, args, message):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match=message):
            await client.call_tool(tool, args)

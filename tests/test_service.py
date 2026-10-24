from datetime import date, timedelta

import pytest
from sqlalchemy import select

import db
import service


def _add(amount, category="food", d=date(2026, 10, 1), description=""):
    return service.add_expense(amount, category, description, d)


# ---------- dates ----------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-10-20", date(2026, 10, 20)),
        ("2026/10/20", date(2026, 10, 20)),
        ("20/10/2026", date(2026, 10, 20)),
        ("20-10-2026", date(2026, 10, 20)),
        ("20 Oct 2026", date(2026, 10, 20)),
        ("October 20, 2026", date(2026, 10, 20)),
        ("  20   Oct  2026 ", date(2026, 10, 20)),  # extra spaces
        ("03/04/2026", date(2026, 4, 3)),  # ambiguous: day first
        ("10/26/2026", date(2026, 10, 26)),  # only valid month first
    ],
)
def test_parse_date_formats(text, expected):
    assert service.parse_date(text) == expected


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError):
        service.parse_date("banana")


# ---------- add ----------


def test_amount_is_stored_as_integer_paise():
    _add(10.55)
    with db.get_engine().connect() as conn:
        assert conn.execute(select(db.expenses.c.amount_paise)).scalar_one() == 1055


def test_amount_round_trips_exactly():
    assert _add(10.55)["amount"] == 10.55


@pytest.mark.parametrize("amount", [0, -5, 0.001])
def test_rejects_non_positive_amount(amount):
    with pytest.raises(ValueError):
        _add(amount)


def test_rejects_unknown_category():
    with pytest.raises(ValueError, match="Unknown category"):
        _add(10, "pizza")


def test_category_is_case_insensitive():
    assert _add(10, "  FOOD ")["category"] == "food"


def test_rejects_future_date():
    with pytest.raises(ValueError, match="future"):
        _add(10, d=service.today() + timedelta(days=1))


def test_description_is_trimmed_and_capped():
    assert _add(10, description="  " + "x" * 300)["description"] == "x" * 200


# ---------- list ----------


def test_list_is_newest_first():
    _add(1, d=date(2026, 10, 2))
    _add(2, d=date(2026, 10, 3))
    _add(3, d=date(2026, 10, 1))
    dates = [e["spent_on_date"] for e in service.list_expenses()]
    assert dates == ["2026-10-03", "2026-10-02", "2026-10-01"]


def test_list_date_range_is_inclusive():
    _add(1, d=date(2026, 10, 1))
    _add(2, d=date(2026, 10, 5))
    _add(3, d=date(2026, 10, 9))
    rows = service.list_expenses(start=date(2026, 10, 1), end=date(2026, 10, 5))
    assert sorted(r["amount"] for r in rows) == [1, 2]


def test_list_filters_by_category():
    _add(1, "food")
    _add(2, "rent")
    rows = service.list_expenses(category="rent")
    assert [r["category"] for r in rows] == ["rent"]


def test_list_respects_limit():
    for i in range(3):
        _add(i + 1)
    assert len(service.list_expenses(limit=2)) == 2


def test_list_rejects_reversed_range():
    with pytest.raises(ValueError):
        service.list_expenses(start=date(2026, 10, 10), end=date(2026, 10, 1))


# ---------- summary ----------


def test_summary_totals_and_order():
    _add(450, "food")
    _add(16000, "rent")
    _add(50, "food")
    s = service.get_summary()
    assert s["total"] == 16500
    assert s["count"] == 3
    assert s["by_category"] == {"rent": 16000, "food": 500}
    assert list(s["by_category"]) == ["rent", "food"]  # largest first


def test_summary_respects_date_range():
    _add(100, d=date(2026, 9, 30))
    _add(200, d=date(2026, 10, 1))
    s = service.get_summary(start=date(2026, 10, 1))
    assert s["total"] == 200


def test_summary_of_empty_database():
    s = service.get_summary()
    assert s["total"] == 0 and s["count"] == 0 and s["by_category"] == {}


# ---------- update ----------


def test_update_changes_only_the_given_field():
    e = _add(450, "food", description="lunch")
    r = service.update_expense(e["id"], amount=350)
    assert r["before"]["amount"] == 450
    assert r["after"]["amount"] == 350
    assert r["after"]["category"] == "food"
    assert r["after"]["description"] == "lunch"


def test_update_several_fields_at_once():
    e = _add(100)
    r = service.update_expense(
        e["id"],
        amount=300,
        category="shopping",
        description="new",
        spent_on_date=date(2026, 10, 2),
    )
    assert r["after"] == {
        "id": e["id"],
        "amount": 300,
        "category": "shopping",
        "description": "new",
        "spent_on_date": "2026-10-02",
    }


def test_update_ignores_empty_strings():
    e = _add(100, "food")
    r = service.update_expense(e["id"], amount=5, category="", description="  ")
    assert r["after"]["amount"] == 5
    assert r["after"]["category"] == "food"


def test_update_with_nothing_to_change_is_an_error():
    e = _add(100)
    with pytest.raises(ValueError, match="Nothing to update"):
        service.update_expense(e["id"])


def test_update_unknown_id():
    with pytest.raises(ValueError, match="No expense"):
        service.update_expense(999, amount=5)


def test_invalid_update_leaves_row_untouched():
    e = _add(100, "food")
    with pytest.raises(ValueError):
        service.update_expense(e["id"], amount=500, category="pizza")
    assert service.list_expenses()[0]["amount"] == 100  # amount NOT changed


# ---------- delete ----------


def test_delete_removes_only_that_row():
    keep = _add(1)
    gone = _add(2)
    deleted = service.delete_expense(gone["id"])
    assert deleted["amount"] == 2
    assert [r["id"] for r in service.list_expenses()] == [keep["id"]]


def test_delete_twice_is_an_error():
    e = _add(1)
    service.delete_expense(e["id"])
    with pytest.raises(ValueError, match="No expense"):
        service.delete_expense(e["id"])


def test_ai_category_is_accepted():
    assert _add(1999, "ai", description="subscription")["category"] == "ai"
    assert [r["category"] for r in service.list_expenses(category="ai")] == ["ai"]

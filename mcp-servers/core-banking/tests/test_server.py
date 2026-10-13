from core_banking.server import (
    _get_account_detail,
    _get_transactions,
    _list_accounts,
    _transfer,
)


def test_list_accounts_returns_customer_accounts():
    accounts = _list_accounts()
    names = {a["name"] for a in accounts}
    assert {"Everyday Checking", "Rainy Day Savings"} <= names
    # Balances are present and numeric; no full account numbers in the summary view.
    assert all(isinstance(a["balance"], (int, float)) for a in accounts)
    assert all("account_number" not in a for a in accounts)


def test_get_transactions_returns_rows_for_an_account():
    rows = _get_transactions("checking")
    assert len(rows) >= 1
    assert {"date", "description", "amount"} <= set(rows[0])


def test_get_account_detail_exposes_full_numbers():
    detail = _get_account_detail("checking")
    assert detail["account_number"].isdigit()
    assert detail["routing_number"].isdigit()


def test_transfer_moves_funds_and_echoes_the_request():
    result = _transfer("savings", "checking", 500)
    assert result["from_account"] == "savings"
    assert result["to_account"] == "checking"
    assert result["amount"] == 500
    assert result["status"] in {"settled", "queued"}

"""Internal "core banking" MCP server - fake-but-relatable account/ledger data
for the auth-pillar demo. Auth is handled by agentgateway in front of this
server; this process has no auth logic of its own and returns the same data
regardless of caller. Tool-level allow/deny is enforced at the gateway (CEL)."""
from mcp.server import FastMCP

mcp = FastMCP(name="core-banking", host="0.0.0.0", port=8000)

_ACCOUNTS = [
    {"id": "checking", "name": "Everyday Checking", "balance": 4210.55, "currency": "USD"},
    {"id": "savings", "name": "Rainy Day Savings", "balance": 18300.00, "currency": "USD"},
]

_TRANSACTIONS = {
    "checking": [
        {"date": "2026-10-11", "description": "Grocer", "amount": -84.20},
        {"date": "2026-10-10", "description": "Payroll", "amount": 3200.00},
        {"date": "2026-10-09", "description": "Electric utility", "amount": -140.75},
    ],
    "savings": [
        {"date": "2026-10-01", "description": "Interest", "amount": 12.40},
        {"date": "2026-09-28", "description": "Transfer in", "amount": 500.00},
    ],
}

# Full account/routing numbers - the sensitive view the demo gates behind RBAC
# at the gateway, and masks on the way out in the guardrails pillar.
_ACCOUNT_DETAIL = {
    "checking": {"account_number": "100042118", "routing_number": "021000021"},
    "savings": {"account_number": "100042119", "routing_number": "021000021"},
}


def _list_accounts() -> list[dict]:
    """Return the customer's accounts with balances (summary view, no full numbers)."""
    return _ACCOUNTS


def _get_transactions(account: str) -> list[dict]:
    """Return recent transactions for one of the customer's accounts."""
    return _TRANSACTIONS.get(account, [])


def _get_account_detail(account: str) -> dict:
    """Return full account and routing numbers for an account (sensitive)."""
    detail = _ACCOUNT_DETAIL.get(account, {})
    return {"account": account, **detail}


def _transfer(from_account: str, to_account: str, amount: float) -> dict:
    """Move funds between two of the customer's accounts (write action)."""
    return {
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "status": "settled",
        "confirmation": f"txn-{from_account}-{to_account}-001",
    }


@mcp.tool()
def list_accounts() -> list[dict]:
    """List the customer's accounts and balances."""
    return _list_accounts()


@mcp.tool()
def get_transactions(account: str) -> list[dict]:
    """Get recent transactions for one of the customer's accounts by id."""
    return _get_transactions(account)


@mcp.tool()
def get_account_detail(account: str) -> dict:
    """Get full account and routing numbers for an account (sensitive)."""
    return _get_account_detail(account)


@mcp.tool()
def transfer(from_account: str, to_account: str, amount: float) -> dict:
    """Move funds between two of the customer's accounts (write action)."""
    return _transfer(from_account, to_account, amount)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

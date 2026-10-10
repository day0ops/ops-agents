"""Internal "repo" MCP server - fake-but-relatable repo/deploy data for the
auth-pillar demo. Auth is handled by agentgateway in front of this server;
this process has no auth logic of its own."""
from mcp.server import FastMCP

mcp = FastMCP(name="repo-server", host="0.0.0.0", port=8000)

_REPOS = [
    {"name": "payments-service", "default_branch": "main", "open_prs": 3},
    {"name": "checkout-web", "default_branch": "main", "open_prs": 1},
    {"name": "fraud-rules", "default_branch": "main", "open_prs": 0},
]


def _list_repos() -> list[dict]:
    """Return the organization's repositories."""
    return _REPOS


def _get_pull_request_status(repo: str, number: int) -> dict:
    """Return the status of a pull request in a repo."""
    return {"repo": repo, "number": number, "state": "open",
            "checks": "passing", "reviewers": ["alice", "bob"]}


def _trigger_deploy(repo: str, environment: str) -> dict:
    """Trigger a deployment of a repo to an environment."""
    return {"repo": repo, "environment": environment, "status": "queued",
            "deploy_id": f"dep-{repo}-{environment}-001"}


@mcp.tool()
def list_repos() -> list[dict]:
    """List the organization's repositories."""
    return _list_repos()


@mcp.tool()
def get_pull_request_status(repo: str, number: int) -> dict:
    """Get the status of a pull request by repo name and PR number."""
    return _get_pull_request_status(repo, number)


@mcp.tool()
def trigger_deploy(repo: str, environment: str) -> dict:
    """Trigger a deployment of a repo to a named environment (write action)."""
    return _trigger_deploy(repo, environment)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

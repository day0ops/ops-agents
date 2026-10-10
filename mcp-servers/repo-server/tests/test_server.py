from repo_server.server import _get_pull_request_status, _list_repos, _trigger_deploy


def test_list_repos_returns_seeded_repos():
    repos = _list_repos()
    names = [r["name"] for r in repos]
    assert "payments-service" in names
    assert all("name" in r and "default_branch" in r for r in repos)


def test_pr_status_shape():
    s = _get_pull_request_status("payments-service", 42)
    assert s["repo"] == "payments-service"
    assert s["number"] == 42
    assert s["state"] in {"open", "merged", "closed"}


def test_trigger_deploy_echoes_target():
    r = _trigger_deploy("payments-service", "staging")
    assert r["repo"] == "payments-service"
    assert r["environment"] == "staging"
    assert r["status"] == "queued"

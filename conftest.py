"""Makes each service's own package importable regardless of where pytest
is invoked from. pyproject.toml's pythonpath only reaches one directory
level below the repo root (agents/, mcp-servers/), but each service's
importable package lives one level below that again (e.g.
mcp-servers/repo-server/repo_server/) - without this, `python -m pytest`
run from the repo root (as ci.yml and the Makefile's test target do)
can't resolve `from repo_server...` even though running pytest from
inside the service's own directory works fine."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent

for group in ("agents", "mcp-servers"):
    group_dir = ROOT / group
    if not group_dir.is_dir():
        continue
    for service_dir in group_dir.iterdir():
        if service_dir.is_dir():
            sys.path.insert(0, str(service_dir))

import pytest

from .conftest import approve_all, create_draft

PAGES = ["/", "/documents", "/documents/SOP-001", "/revisions/1", "/tasks", "/acks", "/equipment", "/export",
         "/checks", "/users", "/audit", "/password", "/submit"]


@pytest.mark.parametrize("role", ["admin", "author", "reviewer", "approver", "viewer"])
def test_all_pages_render_without_server_error(team, role):
    t = team
    create_draft(t["author"], effective="2020-01-01")
    approve_all(t, 1)
    c = t[role]
    for p in PAGES:
        assert c.get(p).status_code in (200, 403, 404), (role, p)

"""Every tenant route, called by tenant A users with tenant B ids, must answer 404."""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import World

PARAM = re.compile(r"{(\w+)}")


def tenant_routes() -> list[tuple[str, str]]:
    spec = create_app().openapi()
    return [
        (method.upper(), path)
        for path, ops in spec["paths"].items()
        if path.startswith("/api/v1/t/{tenant_id}")
        for method in ops
    ]


ROUTES = tenant_routes()


def _call(client: TestClient, method: str, url: str) -> int:
    if method in {"POST", "PATCH", "PUT"}:
        return client.request(method, url, json={}).status_code
    return client.request(method, url).status_code


def _fill(path: str, tenant_id: str, ids: dict[str, str]) -> str:
    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name == "tenant_id":
            return tenant_id
        assert name in ids, f"isolation fixture has no resource for path param {name!r} ({path})"
        return ids[name]

    return PARAM.sub(sub, path)


def test_routes_discovered() -> None:
    assert len(ROUTES) > 30


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_foreign_tenant_path_is_404(world: World, method: str, path: str) -> None:
    """A users addressing tenant B directly."""
    url = _fill(path, world.b.tenant_id, world.b.ids)
    for client in (world.a.fde, world.a.client_admin, world.a.client_user):
        assert _call(client, method, url) == 404, (method, url)


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if len(PARAM.findall(r[1])) > 1])
def test_foreign_resource_id_is_404(world: World, method: str, path: str) -> None:
    """A users addressing B resources through their own tenant prefix."""
    url = _fill(path, world.a.tenant_id, world.b.ids)
    for client in (world.a.fde, world.a.client_admin, world.a.client_user):
        assert _call(client, method, url) == 404, (method, url)


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r[0] == "GET"])
def test_own_resources_are_readable(world: World, method: str, path: str) -> None:
    url = _fill(path, world.a.tenant_id, world.a.ids)
    assert world.a.fde.get(url).status_code == 200, url


def test_unauthenticated_is_401(world: World) -> None:
    anon = TestClient(create_app())
    for method, path in ROUTES:
        url = _fill(path, world.a.tenant_id, world.a.ids)
        assert _call(anon, method, url) == 401, (method, url)

import ast
import os
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"
ADAPTERS = APP / "adapters"
FORBIDDEN = {"httpx", "requests", "urllib.request", "aiohttp", "socket", "anthropic"}
DIST_ALLOWLIST: list[str] = []


def _imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{a.name}" for a in node.names)
    return names


def _is_forbidden(name: str) -> bool:
    return any(name == f or name.startswith(f + ".") for f in FORBIDDEN)


def test_no_network_imports_outside_adapters() -> None:
    offenders = []
    for path in APP.rglob("*.py"):
        if ADAPTERS in path.parents:
            continue
        for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if _is_forbidden(name):
                offenders.append(f"{path.relative_to(BACKEND)}: {name}")
    assert offenders == []


def test_detector_catches_forbidden_imports() -> None:
    for src in ("import httpx", "from urllib.request import urlopen", "import socket", "from anthropic import X"):
        assert any(_is_forbidden(n) for n in _imports(ast.parse(src)))
    assert not any(_is_forbidden(n) for n in _imports(ast.parse("import urllib.parse")))


def test_modules_do_not_import_each_other() -> None:
    modules_dir = APP / "modules"
    offenders = []
    for mod in (p for p in modules_dir.iterdir() if p.is_dir() and not p.name.startswith("__")):
        for path in mod.rglob("*.py"):
            for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
                if name.startswith("app.modules.") and not name.startswith(f"app.modules.{mod.name}"):
                    offenders.append(f"{path.relative_to(BACKEND)}: {name}")
    assert offenders == []


EXTERNAL_REF = re.compile(
    r"""(?:<(?:script|link|img|source|iframe)[^>]+(?:src|href)\s*=\s*["']?|url\(\s*["']?|@import\s+["']|import\(\s*["'])(https?:)?//""",
    re.IGNORECASE,
)


def _dist_dir() -> Path:
    return Path(os.environ.get("FRONTEND_DIST", BACKEND.parent / "frontend" / "dist"))


def test_frontend_dist_has_no_external_resources() -> None:
    dist = _dist_dir()
    if not dist.is_dir():
        if os.environ.get("REQUIRE_FRONTEND_DIST"):
            pytest.fail(f"frontend dist not found at {dist}")
        pytest.skip("frontend dist not built")
    offenders = []
    for path in dist.rglob("*"):
        if path.suffix not in {".html", ".css", ".js", ".svg", ".webmanifest"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in EXTERNAL_REF.finditer(text):
            snippet = text[m.start() : m.end() + 60]
            if not any(a in snippet for a in DIST_ALLOWLIST):
                offenders.append(f"{path.name}: {snippet}")
    assert offenders == []


def test_dist_detector() -> None:
    assert EXTERNAL_REF.search('<script src="https://cdn.example.com/x.js">')
    assert EXTERNAL_REF.search("@font-face{src:url(https://fonts.gstatic.com/a.woff2)}")
    assert EXTERNAL_REF.search('<link rel="stylesheet" href="//fonts.googleapis.com/css">')
    assert not EXTERNAL_REF.search('<script type="module" src="/assets/index.js">')

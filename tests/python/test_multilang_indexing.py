"""End-to-end indexing tests proving the query layer is language-agnostic.

Indexes a small Python (DRF/FastAPI) repo and a Java repo through the real
:class:`Indexer` + SQLite store, then asserts ``list_by_tag('controller')``
returns results for both \u2014 with no language-specific query logic.
"""

from pathlib import Path

from brain.config.default_config import default_config
from brain.core.db.database import Database
from brain.core.db.repositories.symbol_repository import SymbolRepository
from brain.core.embeddings.embedding_provider import get_embedding_provider
from brain.core.indexing.indexer import Indexer

DRF_CONTROLLER = '''
from rest_framework.viewsets import ModelViewSet


class UserViewSet(ModelViewSet):
    def list(self, request):
        return []
'''

FASTAPI_ROUTER = '''
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping():
    return {"ok": True}
'''

JAVA_CONTROLLER = '''
package com.example;

@RestController
@RequestMapping("/users")
public class UserController {

    @GetMapping("/{id}")
    public String get(String id) {
        return id;
    }
}
'''


def _index(repo_root: Path) -> SymbolRepository:
    config = default_config()
    db = Database(repo_root)
    embedder = get_embedding_provider(config)
    Indexer(str(repo_root), db, embedder, config).full_index()
    return SymbolRepository(db)


def test_python_controllers_indexed_and_queryable(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "controllers.py").write_text(DRF_CONTROLLER, encoding="utf-8")
    (tmp_path / "app" / "users_router.py").write_text(FASTAPI_ROUTER, encoding="utf-8")

    symbols = _index(tmp_path)

    controllers = {r["name"] for r in symbols.list_by_tag("controller")}
    assert "UserViewSet" in controllers
    assert "ping" in controllers  # router handler in a *_router.py module
    # Routes are queryable structurally too.
    assert symbols.count_by_tag("route") >= 1


def test_java_controllers_still_indexed(tmp_path: Path):
    (tmp_path / "UserController.java").write_text(JAVA_CONTROLLER, encoding="utf-8")

    symbols = _index(tmp_path)

    controllers = {r["name"] for r in symbols.list_by_tag("controller")}
    assert "UserController" in controllers

"""Tests for language-agnostic tagging of Python web frameworks.

Uses ``symbol_extractor.extract`` so the neutral provenance fields
(``language``/``file_path``) are populated before the registered Python tagger
runs \u2014 exactly as during indexing.
"""

import json

from brain.core.indexing import symbol_extractor

FASTAPI_SOURCE = '''
from fastapi import APIRouter

router = APIRouter()


@router.get("/users/{id}")
async def get_user(id: int):
    return {"id": id}
'''

FLASK_SOURCE = '''
from flask import Blueprint

bp = Blueprint("bp", __name__)


@bp.route("/health")
def health():
    return "ok"
'''

DRF_SOURCE = '''
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView


class UserViewSet(ModelViewSet):
    def list(self, request):
        return []


class PingView(APIView):
    def get(self, request):
        return {}
'''

STEREOTYPE_SOURCE = '''
class PaymentService:
    def charge(self):
        return True


class UserRepository:
    def find(self, id):
        return None
'''


def _tags_by_name(source, path):
    result = symbol_extractor.extract(source, path, "python")
    return {s.name: set(s.tags) for s in result.symbols}


def test_fastapi_router_handler_tagged_controller_and_route():
    tags = _tags_by_name(FASTAPI_SOURCE, "app/users_router.py")
    assert "route" in tags["get_user"]
    assert "api" in tags["get_user"]
    # Router handlers in a *_router.py module count as controllers.
    assert "controller" in tags["get_user"]


def test_flask_route_handler_tagged_controller():
    tags = _tags_by_name(FLASK_SOURCE, "app/views.py")
    assert "route" in tags["health"]
    assert "controller" in tags["health"]


def test_drf_class_views_tagged_controller():
    tags = _tags_by_name(DRF_SOURCE, "app/controllers.py")
    assert "controller" in tags["UserViewSet"]
    assert "controller" in tags["PingView"]
    assert "api" in tags["UserViewSet"]


def test_service_and_repository_naming():
    tags = _tags_by_name(STEREOTYPE_SOURCE, "app/domain.py")
    assert "service" in tags["PaymentService"]
    assert "repository" in tags["UserRepository"]


def test_metadata_json_serialized_for_routes():
    result = symbol_extractor.extract(FASTAPI_SOURCE, "app/users_router.py", "python")
    rows = symbol_extractor.to_symbol_rows(result)
    row = next(r for r in rows if r["name"] == "get_user")
    meta = json.loads(row["metadata_json"])
    assert meta["http_method"] == "GET"
    assert meta["decorator"] == "router.get"

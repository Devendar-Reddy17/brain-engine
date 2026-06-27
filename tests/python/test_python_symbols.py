"""Tests for Python symbol extraction via the stdlib ``ast`` parser.

These exercise the neutral facts the parser must produce (classes, functions,
methods, decorators, inheritance, routes, tests) independent of tagging.
"""

from brain.core.parsing.python_parser import PythonParser

FASTAPI_SOURCE = '''
from fastapi import APIRouter

router = APIRouter()


@router.get("/users/{id}")
async def get_user(id: int):
    return {"id": id}


@router.post("/users")
def create_user(body: dict):
    return body
'''

FLASK_SOURCE = '''
from flask import Blueprint

bp = Blueprint("bp", __name__)


@bp.route("/health")
def health():
    return "ok"


@app.route("/submit", methods=["POST"])
def submit():
    return "done"
'''

DRF_SOURCE = '''
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView


class UserViewSet(ModelViewSet):
    queryset = []

    def list(self, request):
        return []


class PingView(APIView):
    def get(self, request):
        return {}
'''

MISC_SOURCE = '''
def helper(x):
    return x


def test_helper():
    assert helper(1) == 1


class TestThings:
    def test_one(self):
        assert True
'''


def _parse(source, path):
    return PythonParser().parse(source, path)


def test_fastapi_routes_extracted():
    result = _parse(FASTAPI_SOURCE, "app/users_router.py")
    routes = [s for s in result.symbols if s.kind == "route"]
    names = {s.name for s in routes}
    assert {"get_user", "create_user"} <= names
    get_user = next(s for s in routes if s.name == "get_user")
    assert get_user.route == "GET /users/{id}"
    assert get_user.framework_metadata.get("http_method") == "GET"
    assert "router.get" in get_user.annotations


def test_flask_routes_extracted():
    result = _parse(FLASK_SOURCE, "app/views.py")
    routes = {s.name: s for s in result.symbols if s.kind == "route"}
    assert "health" in routes and "submit" in routes
    assert routes["health"].route == "GET /health"
    assert routes["submit"].route == "POST /submit"
    assert routes["submit"].framework_metadata.get("decorator") == "app.route"


def test_drf_classes_and_inheritance():
    result = _parse(DRF_SOURCE, "app/controllers.py")
    classes = {s.name: s for s in result.symbols if s.kind == "class"}
    assert "UserViewSet" in classes and "PingView" in classes
    assert "ModelViewSet" in classes["UserViewSet"].extends
    assert "APIView" in classes["PingView"].extends
    # Methods carry their parent class.
    methods = [s for s in result.symbols if s.kind == "method"]
    assert any(m.name == "list" and m.parent_symbol == "UserViewSet" for m in methods)


def test_functions_and_tests():
    result = _parse(MISC_SOURCE, "app/util.py")
    helper = next(s for s in result.symbols if s.name == "helper")
    assert helper.kind == "function"
    assert helper.signature == "helper(x)"
    test_fn = next(s for s in result.symbols if s.name == "test_helper")
    assert test_fn.kind == "test" and test_fn.is_test
    # A test method inside a Test* class is detected too.
    method_test = next(s for s in result.symbols if s.name == "test_one")
    assert method_test.is_test


def test_imports_recorded():
    result = _parse(DRF_SOURCE, "app/controllers.py")
    assert "rest_framework.viewsets.ModelViewSet" in result.imports
    assert result.package == "app.controllers"


def test_syntax_error_degrades_gracefully():
    result = _parse("def broken(:\n", "bad.py")
    assert result.language == "python"
    assert result.symbols == []

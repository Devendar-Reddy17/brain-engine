"""Tests for the QueryPlanner routing layer.

Uses lightweight fake repositories (duck-typed) so the planner can be tested
without a real SQLite database.
"""

from brain.core.query.query_planner import QueryContext, QueryPlanner


class FakeSymbols:
    def __init__(self, by_tag=None, by_kind=None, by_name=None, kind_counts=None, all_rows=None):
        self._by_tag = by_tag or {}
        self._by_kind = by_kind or {}
        self._by_name = by_name or []
        self._kind_counts = kind_counts or []
        self._all_rows = all_rows or []

    def list_by_tag(self, tag, limit=500):
        return self._by_tag.get(tag, [])

    def count_by_tag(self, tag):
        return len(self._by_tag.get(tag, []))

    def list_by_kind(self, kind, limit=500):
        return self._by_kind.get(kind, [])

    def count_by_kind(self, kind):
        return len(self._by_kind.get(kind, []))

    def counts_by_kind(self):
        return self._kind_counts

    def search_by_name(self, term, limit=20):
        return [r for r in self._by_name if term and term.lower() in str(r["name"]).lower()]

    def find_by_name(self, name, limit=20):
        return [r for r in self._by_name if r["name"] == name]

    def list_all(self, limit=5000):
        return self._all_rows


class FakeDeps:
    def __init__(self, by_edge=None, imports=None):
        self._by_edge = by_edge or {}
        self._imports = imports or []

    def list_by_edge_type(self, edge_type, limit=500):
        return self._by_edge.get(edge_type, [])

    def imports_for_file(self, file_path_like, limit=500):
        return self._imports


def _row(**kwargs):
    return kwargs


def _planner(symbols=None, deps=None, is_stale=False):
    ctx = QueryContext(
        symbols=symbols or FakeSymbols(),
        deps=deps or FakeDeps(),
        is_stale=is_stale,
    )
    return QueryPlanner(ctx)


# -- local routing ---------------------------------------------------------
def test_count_controllers_is_local():
    symbols = FakeSymbols(by_tag={"controller": [_row(name="AuthController", kind="class",
                                                      file_path="A.java", start_line=1, end_line=9,
                                                      tags_json='["controller"]', annotations_json='[]')]})
    plan = _planner(symbols=symbols).plan("How many controllers are in this repository?")
    assert plan.execution_path == "local"
    assert plan.local_result.count == 1
    assert plan.local_result.items[0].name == "AuthController"


def test_list_services_is_local():
    symbols = FakeSymbols(by_tag={"service": [_row(name="UserService", kind="class",
                                                   file_path="U.java", start_line=1, end_line=9)]})
    plan = _planner(symbols=symbols).plan("List all Spring services.")
    assert plan.execution_path == "local"
    assert plan.local_result.title == "Services"


def test_find_named_symbol_is_local_not_service_tag():
    symbols = FakeSymbols(by_name=[_row(name="PaymentService", kind="class",
                                        file_path="P.java", start_line=3, end_line=9)])
    plan = _planner(symbols=symbols).plan("Find PaymentService.")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "find_symbol"
    assert plan.local_result.items[0].name == "PaymentService"


def test_show_rest_endpoints_is_local():
    deps = FakeDeps(by_edge={"routes_to": [_row(target_symbol_name="GET /users", source_name="list",
                                                source_file="C.java", source_start_line=10,
                                                source_end_line=12)]})
    plan = _planner(deps=deps).plan("Show all REST endpoints.")
    assert plan.execution_path == "local"
    assert plan.local_result.items[0].name == "GET /users"


def test_which_package_contains_is_local():
    symbols = FakeSymbols(by_name=[_row(name="UserController", kind="class",
                                        file_path="com/x/UserController.java", start_line=1, end_line=9)])
    plan = _planner(symbols=symbols).plan("Which package contains UserController?")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "which_package"


# -- AI routing ------------------------------------------------------------
def test_explain_is_ai_required():
    plan = _planner().plan("Explain the authentication flow.")
    assert plan.execution_path == "ai_required"


def test_refactor_is_ai_required():
    plan = _planner().plan("Suggest a refactoring for the payment module.")
    assert plan.execution_path == "ai_required"


def test_why_is_ai_required():
    plan = _planner().plan("Why is this design used?")
    assert plan.execution_path == "ai_required"


def test_unmatched_question_is_ai_required():
    # No enumeration cue and no handler match -> conservative fallback.
    plan = _planner().plan("The payment module feels slow.")
    assert plan.execution_path == "ai_required"


# -- stale handling --------------------------------------------------------
def test_stale_tag_query_returns_local_with_warning_not_ai():
    symbols = FakeSymbols(by_tag={"controller": []})
    plan = _planner(symbols=symbols, is_stale=True).plan("How many controllers are there?")
    # Deterministic count/list queries must NOT fall back to AI when stale.
    assert plan.execution_path == "local"
    assert plan.local_result.stale_warning is not None


def test_stale_does_not_warn_for_structural_routes():
    deps = FakeDeps(by_edge={"routes_to": []})
    plan = _planner(deps=deps, is_stale=True).plan("Show all routes.")
    assert plan.execution_path == "local"
    # Routes are structural (kind/dependency based), independent of tags_json.
    assert plan.local_result.stale_warning is None


# -- grouped routes: intent routing ----------------------------------------
def test_how_many_controllers_routes_to_controller_handler():
    """'how many controllers' must NOT be swallowed by the grouped handler."""
    symbols = FakeSymbols(by_tag={"controller": [_row(name="AuthController", kind="class",
                                                      file_path="A.java", start_line=1, end_line=9,
                                                      tags_json='["controller"]')]})
    plan = _planner(symbols=symbols).plan("How many controllers are in this repository?")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "tag:controller"
    assert plan.local_result.count == 1


def test_show_routes_grouped_by_controller_routes_to_grouped():
    symbols = FakeSymbols(
        by_tag={"route": [_row(name="GET /users", kind="method", file_path="UserController.java",
                               start_line=15, end_line=20, parent_symbol="listUsers",
                               tags_json='["route"]')]},
        all_rows=[
            _row(name="UserController", kind="class", file_path="UserController.java",
                 start_line=1, end_line=50, parent_symbol=None, tags_json='["controller"]'),
            _row(name="listUsers", kind="method", file_path="UserController.java",
                 start_line=15, end_line=20, parent_symbol="UserController", tags_json='[]'),
            _row(name="GET /users", kind="method", file_path="UserController.java",
                 start_line=15, end_line=20, parent_symbol="listUsers", tags_json='["route"]'),
        ],
    )
    plan = _planner(symbols=symbols).plan("Show all routes grouped by controller")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "grouped_routes"
    assert plan.local_result.count == 1


def test_group_rest_endpoints_by_controller_routes_to_grouped():
    symbols = FakeSymbols(by_tag={"route": []})
    plan = _planner(symbols=symbols).plan("Group REST endpoints by controller")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "grouped_routes"


def test_show_endpoints_grouped_by_owning_class_routes_to_grouped():
    symbols = FakeSymbols(by_tag={"route": []})
    plan = _planner(symbols=symbols).plan("Show endpoints grouped by owning class")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "grouped_routes"


def test_show_routes_grouped_by_router_routes_to_grouped():
    symbols = FakeSymbols(by_tag={"route": []})
    plan = _planner(symbols=symbols).plan("Show routes grouped by router")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "grouped_routes"


def test_show_handlers_grouped_by_module_routes_to_grouped():
    symbols = FakeSymbols(by_tag={"route": []})
    plan = _planner(symbols=symbols).plan("Show handlers grouped by module")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "grouped_routes"


# -- grouped routes: output with multi-language fixtures --------------------
def test_grouped_output_java_spring():
    """Java Spring: controller class owns route methods via parent_symbol chain."""
    symbols = FakeSymbols(
        by_tag={
            "route": [
                _row(name="GET /api/users", kind="method", file_path="UserController.java",
                     start_line=20, end_line=25, parent_symbol="listUsers",
                     tags_json='["route"]'),
                _row(name="POST /api/users", kind="method", file_path="UserController.java",
                     start_line=30, end_line=35, parent_symbol="createUser",
                     tags_json='["route"]'),
            ],
            "controller": [
                _row(name="UserController", kind="class", file_path="UserController.java",
                     start_line=1, end_line=50, parent_symbol=None,
                     tags_json='["controller"]'),
            ],
        },
        all_rows=[
            _row(name="UserController", kind="class", file_path="UserController.java",
                 start_line=1, end_line=50, parent_symbol=None, tags_json='["controller"]'),
            _row(name="listUsers", kind="method", file_path="UserController.java",
                 start_line=20, end_line=25, parent_symbol="UserController", tags_json='[]'),
            _row(name="createUser", kind="method", file_path="UserController.java",
                 start_line=30, end_line=35, parent_symbol="UserController", tags_json='[]'),
            _row(name="GET /api/users", kind="method", file_path="UserController.java",
                 start_line=20, end_line=25, parent_symbol="listUsers", tags_json='["route"]'),
            _row(name="POST /api/users", kind="method", file_path="UserController.java",
                 start_line=30, end_line=35, parent_symbol="createUser", tags_json='["route"]'),
        ],
    )
    plan = _planner(symbols=symbols).plan("Show all routes grouped by controller")
    assert plan.execution_path == "local"
    result = plan.local_result
    assert result.query_type == "grouped_routes"
    assert result.count == 2
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.owner == "UserController"
    assert group.owner_kind == "class"
    assert len(group.items) == 2
    names = {i.name for i in group.items}
    assert names == {"GET /api/users", "POST /api/users"}


def test_grouped_output_python_fastapi():
    """FastAPI: router module owns route functions via parent_symbol."""
    symbols = FakeSymbols(
        by_tag={
            "route": [
                _row(name="GET /items", kind="function", file_path="routers/items.py",
                     start_line=10, end_line=15, parent_symbol=None,
                     tags_json='["route"]'),
                _row(name="POST /items", kind="function", file_path="routers/items.py",
                     start_line=20, end_line=25, parent_symbol=None,
                     tags_json='["route"]'),
            ],
        },
        all_rows=[
            _row(name="router", kind="variable", file_path="routers/items.py",
                 start_line=1, end_line=5, parent_symbol=None, tags_json='["router"]'),
            _row(name="get_items", kind="function", file_path="routers/items.py",
                 start_line=10, end_line=15, parent_symbol=None, tags_json='["route"]'),
            _row(name="create_item", kind="function", file_path="routers/items.py",
                 start_line=20, end_line=25, parent_symbol=None, tags_json='["route"]'),
            _row(name="GET /items", kind="function", file_path="routers/items.py",
                 start_line=10, end_line=15, parent_symbol=None, tags_json='["route"]'),
            _row(name="POST /items", kind="function", file_path="routers/items.py",
                 start_line=20, end_line=25, parent_symbol=None, tags_json='["route"]'),
        ],
    )
    plan = _planner(symbols=symbols).plan("Show routes grouped by router")
    assert plan.execution_path == "local"
    result = plan.local_result
    assert result.query_type == "grouped_routes"
    assert result.count == 2
    # No parent_symbol on routes → enclosing-symbol inference should find "router"
    # (start_line=1, end_line=5) which encloses lines 10-15? No — it doesn't
    # enclose. So fallback to file path.
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.owner == "routers/items.py"


def test_grouped_output_flask_blueprint():
    """Flask: blueprint routes with parent_symbol set to blueprint name."""
    symbols = FakeSymbols(
        by_tag={
            "route": [
                _row(name="GET /auth/login", kind="function", file_path="auth/routes.py",
                     start_line=12, end_line=18, parent_symbol="auth_bp",
                     tags_json='["route"]'),
                _row(name="POST /auth/logout", kind="function", file_path="auth/routes.py",
                     start_line=22, end_line=28, parent_symbol="auth_bp",
                     tags_json='["route"]'),
            ],
        },
        all_rows=[
            _row(name="auth_bp", kind="variable", file_path="auth/routes.py",
                 start_line=1, end_line=5, parent_symbol=None, tags_json='["blueprint"]'),
            _row(name="login", kind="function", file_path="auth/routes.py",
                 start_line=12, end_line=18, parent_symbol="auth_bp", tags_json='["route"]'),
            _row(name="logout", kind="function", file_path="auth/routes.py",
                 start_line=22, end_line=28, parent_symbol="auth_bp", tags_json='["route"]'),
            _row(name="GET /auth/login", kind="function", file_path="auth/routes.py",
                 start_line=12, end_line=18, parent_symbol="auth_bp", tags_json='["route"]'),
            _row(name="POST /auth/logout", kind="function", file_path="auth/routes.py",
                 start_line=22, end_line=28, parent_symbol="auth_bp", tags_json='["route"]'),
        ],
    )
    plan = _planner(symbols=symbols).plan("Show endpoints grouped by owning class")
    assert plan.execution_path == "local"
    result = plan.local_result
    assert result.query_type == "grouped_routes"
    assert result.count == 2
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.owner == "auth_bp"
    assert len(group.items) == 2


def test_grouped_output_nestjs_controller():
    """NestJS-style: controller class owns route methods via parent_symbol chain."""
    symbols = FakeSymbols(
        by_tag={
            "route": [
                _row(name="GET /users", kind="method", file_path="users.controller.ts",
                     start_line=10, end_line=15, parent_symbol="findAll",
                     tags_json='["route"]'),
            ],
            "controller": [
                _row(name="UsersController", kind="class", file_path="users.controller.ts",
                     start_line=1, end_line=30, parent_symbol=None,
                     tags_json='["controller"]'),
            ],
        },
        all_rows=[
            _row(name="UsersController", kind="class", file_path="users.controller.ts",
                 start_line=1, end_line=30, parent_symbol=None, tags_json='["controller"]'),
            _row(name="findAll", kind="method", file_path="users.controller.ts",
                 start_line=10, end_line=15, parent_symbol="UsersController", tags_json='[]'),
            _row(name="GET /users", kind="method", file_path="users.controller.ts",
                 start_line=10, end_line=15, parent_symbol="findAll", tags_json='["route"]'),
        ],
    )
    plan = _planner(symbols=symbols).plan("Show all routes grouped by controller")
    assert plan.execution_path == "local"
    result = plan.local_result
    assert result.query_type == "grouped_routes"
    assert result.count == 1
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.owner == "UsersController"
    assert group.owner_kind == "class"
    assert len(group.items) == 1


def test_grouped_output_empty_routes():
    """No route symbols → empty groups, count=0."""
    symbols = FakeSymbols(by_tag={"route": []}, all_rows=[])
    plan = _planner(symbols=symbols).plan("Show all routes grouped by controller")
    assert plan.execution_path == "local"
    assert plan.local_result.count == 0
    assert plan.local_result.groups == []


# -- "where is" handler -----------------------------------------------------
def test_where_is_routes_to_local():
    """'where is X' should be handled locally, not fall through to AI."""
    symbols = FakeSymbols(by_name=[_row(name="VerificationController", kind="class",
                                        file_path="VerificationController.java", start_line=1, end_line=50)])
    plan = _planner(symbols=symbols).plan("where is VerificationController")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "where_is"
    assert plan.local_result.count == 1
    assert plan.local_result.items[0].name == "VerificationController"


def test_where_is_falls_back_to_partial_match():
    """If exact match fails, 'where is X' should try partial (LIKE) match."""
    symbols = FakeSymbols(
        by_name=[],  # no exact matches
        # search_by_name uses substring match (see FakeSymbols)
    )
    # FakeSymbols.search_by_name filters by substring on _by_name
    symbols._by_name = [_row(name="VerificationController", kind="class",
                             file_path="VerificationController.java", start_line=1, end_line=50)]
    plan = _planner(symbols=symbols).plan("where is VerificationController")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "where_is"
    assert plan.local_result.count == 1


def test_where_is_with_route_pattern():
    """'where is /api/verifications/{id}' should extract the route and search."""
    symbols = FakeSymbols(
        by_name=[_row(name="/api/verifications/{id}", kind="route",
                      file_path="VerificationController.java", start_line=20, end_line=30)],
    )
    plan = _planner(symbols=symbols).plan("where is /api/verifications/{id}")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "where_is"


def test_where_is_kafka_symbol():
    """Generic: 'where is KafkaConsumer' should work for any symbol name."""
    symbols = FakeSymbols(
        by_name=[_row(name="KafkaConsumer", kind="class",
                      file_path="kafka/consumer.py", start_line=1, end_line=100)],
    )
    plan = _planner(symbols=symbols).plan("where is KafkaConsumer")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "where_is"
    assert plan.local_result.items[0].name == "KafkaConsumer"


# -- specific entity must not be swallowed by broad category handlers ------
def test_specific_route_does_not_dump_all_routes():
    """The reported bug: naming a specific route must not list every route.

    'where this route is present GET /api/verifications/{id}' contains the word
    'route', which previously matched the broad routes handler and dumped all
    endpoints. It now defers to the retrieval/AI pipeline.
    """
    deps = FakeDeps(by_edge={"routes_to": [
        _row(target_symbol_name="GET /api/verifications/{id}", source_name="getById",
             source_file="VerificationController.java", source_start_line=20, source_end_line=25),
        _row(target_symbol_name="GET /api/payments", source_name="listPayments",
             source_file="PaymentController.java", source_start_line=10, source_end_line=15),
    ]})
    plan = _planner(deps=deps).plan("where this route is present GET /api/verifications/{id}")
    assert plan.execution_path == "ai_required"
    assert plan.local_result is None


def test_general_routes_listing_still_local():
    """Without a specific entity, 'show all routes' still answers locally."""
    deps = FakeDeps(by_edge={"routes_to": [_row(target_symbol_name="GET /users", source_name="list",
                                                source_file="C.java", source_start_line=10,
                                                source_end_line=12)]})
    plan = _planner(deps=deps).plan("Show all REST endpoints.")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "routes"


def test_specific_service_path_not_dumped_as_category():
    """Generic: naming a specific path must bypass the broad service handler too."""
    symbols = FakeSymbols(by_tag={"service": [_row(name="PaymentService", kind="class",
                                                   file_path="P.java", start_line=1, end_line=9)]})
    plan = _planner(symbols=symbols).plan("which service handles /api/payments/refund")
    assert plan.execution_path == "ai_required"


def test_quoted_specific_term_bypasses_controller_dump():
    """A quoted specific term must not trigger the broad controllers handler."""
    symbols = FakeSymbols(by_tag={"controller": [_row(name="AuthController", kind="class",
                                                      file_path="A.java", start_line=1, end_line=9,
                                                      tags_json='["controller"]')]})
    plan = _planner(symbols=symbols).plan('which controller defines "loginWithOtp"')
    assert plan.execution_path == "ai_required"


def test_where_is_does_not_swallow_controller_query():
    """'where is AuthController' should route to where_is, not controller tag handler."""
    symbols = FakeSymbols(
        by_name=[_row(name="AuthController", kind="class",
                      file_path="AuthController.java", start_line=1, end_line=50)],
        by_tag={"controller": [_row(name="AuthController", kind="class",
                                    file_path="AuthController.java", start_line=1, end_line=50,
                                    tags_json='["controller"]')]},
    )
    plan = _planner(symbols=symbols).plan("where is AuthController")
    assert plan.execution_path == "local"
    assert plan.local_result.query_type == "where_is"
    # Should NOT be tag:controller
    assert plan.local_result.query_type != "tag:controller"

"""Python web-framework tagger (FastAPI, Flask, Django/DRF).

Maps neutral Python symbol metadata (base classes, decorators, route info,
module/class naming) to normalized stereotype tags. Structural ``route``/``api``
and ``test`` tags are added by the shared derivation in
:mod:`brain.core.parsing.tagging`; this tagger contributes ``controller``,
``service`` and ``repository``.

Conventions covered:
  * Django/DRF class-based views (APIView, ViewSet, ModelViewSet, generics,
    Django generic views) -> ``controller``.
  * Classes named ``*Controller`` / ``*ViewSet`` -> ``controller``.
  * Classes/handlers defined in controller/router modules
    (``*_controller.py``, ``*_router.py``, ``controllers.py``, ``views.py``,
    ``routes.py``, ``router.py``) -> ``controller`` where reasonable.
  * Flask ``@app.route`` / ``@blueprint.route`` handlers -> ``controller``.
  * FastAPI router handlers in router/controller modules -> ``controller``.
  * Classes named ``*Service`` / ``*Repository`` -> ``service`` / ``repository``.
"""

from __future__ import annotations

import posixpath

from brain.core.parsing.parser import ParsedSymbol

LANGUAGE = "python"

# Base classes that mark a class as an HTTP controller (DRF + Django views).
WEB_VIEW_BASES: frozenset[str] = frozenset(
    {
        # Django REST Framework
        "APIView",
        "ViewSet",
        "ViewSetMixin",
        "GenericViewSet",
        "ModelViewSet",
        "ReadOnlyModelViewSet",
        "GenericAPIView",
        "ListAPIView",
        "CreateAPIView",
        "RetrieveAPIView",
        "UpdateAPIView",
        "DestroyAPIView",
        "ListCreateAPIView",
        "RetrieveUpdateAPIView",
        "RetrieveDestroyAPIView",
        "RetrieveUpdateDestroyAPIView",
        # Django generic class-based views
        "View",
        "TemplateView",
        "ListView",
        "DetailView",
        "CreateView",
        "UpdateView",
        "DeleteView",
        "FormView",
        "RedirectView",
    }
)

# Module basenames that conventionally hold HTTP handlers.
_CONTROLLER_MODULES: frozenset[str] = frozenset(
    {"controllers.py", "views.py", "routes.py", "router.py", "api.py"}
)


def _base_name(raw: str) -> str:
    """Last dotted segment of a base class, without generics, e.g.
    ``viewsets.ModelViewSet`` -> ``ModelViewSet``."""

    name = raw.split("[")[0].strip()
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    return name


def _is_controller_module(file_path: str) -> bool:
    if not file_path:
        return False
    fp = file_path.replace("\\", "/").lower()
    base = posixpath.basename(fp)
    if base in _CONTROLLER_MODULES:
        return True
    stem = base[:-3] if base.endswith(".py") else base
    return stem.endswith("_controller") or stem.endswith("_router")


def derive(symbol: ParsedSymbol) -> list[str]:
    tags: list[str] = []
    name = symbol.name or ""
    in_controller_module = _is_controller_module(symbol.file_path)

    if symbol.kind == "class":
        bases = {_base_name(b) for b in symbol.extends}
        if bases & WEB_VIEW_BASES:
            tags.append("controller")
        elif name.endswith("Controller") or name.endswith("ViewSet"):
            tags.append("controller")
        elif name.endswith("View") and name != "View":
            tags.append("controller")
        elif in_controller_module:
            tags.append("controller")

        if name.endswith("Service"):
            tags.append("service")
        if name.endswith("Repository") or name.endswith("Repo"):
            tags.append("repository")
    else:
        # Function/method handlers. Route + api are added structurally; here we
        # decide whether the handler also represents a controller endpoint.
        if symbol.route is not None:
            decorator = str(symbol.framework_metadata.get("decorator", ""))
            # Flask: @app.route / @blueprint.route handlers are controllers.
            if decorator.endswith(".route") or decorator == "route":
                tags.append("controller")
            # FastAPI: router/app handlers living in a router/controller module.
            elif in_controller_module:
                tags.append("controller")

    if "controller" in tags:
        tags.append("api")
    return tags

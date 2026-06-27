"""Core domain types for Local Code Brain.

These Pydantic models mirror the TypeScript types in
``packages/shared/src/schemas/brainTypes.ts``. JSON is serialized using
camelCase aliases so the wire format matches the TypeScript contracts, while
Python code can use snake_case field names.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model that serializes/deserializes using camelCase JSON aliases."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class Intent(str, Enum):
    QUESTION = "question"
    CODE_EDIT = "code_edit"
    TEST_CREATION = "test_creation"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    REVIEW = "review"
    ARCHITECTURE_EXPLANATION = "architecture_explanation"


class SymbolKind(str, Enum):
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    METHOD = "method"
    FUNCTION = "function"
    CONSTRUCTOR = "constructor"
    FIELD = "field"
    CONSTANT = "constant"
    IMPORT = "import"
    PACKAGE = "package"
    ANNOTATION = "annotation"
    ROUTE = "route"
    TEST = "test"
    BEAN = "bean"
    CONFIG = "config"


class Visibility(str, Enum):
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
    PACKAGE = "package"
    UNKNOWN = "unknown"


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    REFERENCES = "references"
    TESTED_BY = "tested_by"
    CONFIGURES = "configures"
    ROUTES_TO = "routes_to"


class ChangeEventType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class RelevantFile(CamelModel):
    path: str
    reason: str


class TargetSymbol(CamelModel):
    name: str
    kind: SymbolKind
    file: str
    start_line: int
    end_line: int


class ContextChunk(CamelModel):
    file: str
    symbol: Optional[str] = None
    start_line: int
    end_line: int
    reason: str
    content: str


class DependencyContext(CamelModel):
    callers: list[str] = []
    callees: list[str] = []
    interfaces: list[str] = []
    implementations: list[str] = []
    configs: list[str] = []
    routes: list[str] = []
    tests: list[str] = []


class TokenSavings(CamelModel):
    """Local, offline token-reduction metrics produced by the retrieval pipeline."""

    repo_tokens: int
    context_tokens: int
    reduction_percentage: float


class LocalQueryItem(CamelModel):
    """A single navigable result from a local (non-AI) repository query."""

    name: str
    kind: str = ""
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    parent_symbol: Optional[str] = None
    annotations: list[str] = []
    tags: list[str] = []


class LocalQueryGroup(CamelModel):
    """A group of child symbols sharing the same owner/parent."""

    owner: str
    owner_kind: str = ""
    owner_file: str = ""
    items: list[LocalQueryItem] = []


class LocalQueryResult(CamelModel):
    """Structured answer produced entirely from the local Brain index."""

    query_type: str
    title: str
    count: int
    items: list[LocalQueryItem] = []
    groups: list[LocalQueryGroup] = []
    stale_warning: Optional[str] = None

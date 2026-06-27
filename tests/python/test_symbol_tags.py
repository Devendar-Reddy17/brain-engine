"""Tests for language-agnostic tag derivation and symbol-row serialization.

Uses the regex FallbackJavaParser via symbol_extractor so the tests do not
require the native tree-sitter grammar.
"""

import json

from brain.core.indexing import symbol_extractor
from brain.core.parsing.fallback_java_parser import FallbackJavaParser
from brain.core.parsing import tagging
from brain.core.parsing.parser import ParsedSymbol

SAMPLE = """
package com.example.shop;

import org.springframework.stereotype.Service;

@Service
public class PaymentService {

    @GetMapping("/pay")
    public String pay() {
        return "ok";
    }

    @Test
    public void testPay() {
        pay();
    }
}
"""


def _extract():
    # symbol_extractor.extract derives tags in one shared place after parsing.
    parser = FallbackJavaParser()
    result = parser.parse(SAMPLE, "PaymentService.java")
    for sym in result.symbols:
        sym.tags = tagging.derive_tags(sym, result.language)
    return result


def test_service_class_tagged_service():
    result = _extract()
    cls = next(s for s in result.symbols if s.name == "PaymentService" and s.kind == "class")
    assert "service" in cls.tags


def test_route_method_tagged_route_and_api():
    result = _extract()
    routes = [s for s in result.symbols if s.kind == "route"]
    assert routes, "expected a route handler"
    assert "route" in routes[0].tags
    assert "api" in routes[0].tags


def test_test_method_tagged_test():
    result = _extract()
    tests = [s for s in result.symbols if s.is_test]
    assert tests
    assert "test" in tests[0].tags


def test_controller_annotations_map_to_controller_tag():
    sym = ParsedSymbol(name="UserController", kind="class", start_line=1, end_line=2,
                       annotations=["RestController"])
    tags = tagging.derive_tags(sym, "java")
    assert "controller" in tags
    assert "api" in tags


def test_typescript_component_annotation_maps_to_component_tag():
    sym = ParsedSymbol(
        name="UserProfileComponent",
        kind="class",
        start_line=1,
        end_line=2,
        annotations=["Component"],
        language="typescript",
        file_path="src/app/users/user-profile.component.ts",
    )
    tags = tagging.derive_tags(sym, "typescript")
    assert "component" in tags
    assert "ui" in tags


def test_react_component_name_maps_to_component_tag():
    sym = ParsedSymbol(
        name="UserCard",
        kind="function",
        start_line=1,
        end_line=2,
        language="typescript",
        file_path="src/features/users/UserCard.tsx",
    )
    tags = tagging.derive_tags(sym, "typescript")
    assert "component" in tags


def test_to_symbol_rows_serializes_annotations_and_tags():
    result = _extract()
    rows = symbol_extractor.to_symbol_rows(result)
    cls_row = next(r for r in rows if r["name"] == "PaymentService")
    tags = json.loads(cls_row["tags_json"])
    annotations = json.loads(cls_row["annotations_json"])
    assert "service" in tags
    assert "Service" in annotations


def test_tagger_version_is_single_source():
    # tagging re-exports the constant; it must equal the one in versions.
    from brain.core import versions

    assert tagging.TAGGER_VERSION == versions.TAGGER_VERSION

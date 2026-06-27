"""Spring/Spring Boot annotation knowledge shared by the Java parsers.

Kept dependency-free (no tree-sitter import) so the regex fallback can use it
even when the native grammar is unavailable.
"""

from __future__ import annotations

# Class-level stereotype annotations.
STEREOTYPE_ANNOTATIONS: frozenset[str] = frozenset(
    {
        "RestController",
        "Controller",
        "Service",
        "Repository",
        "Component",
        "Configuration",
    }
)

# Method/field-level annotations of interest.
INJECTION_ANNOTATIONS: frozenset[str] = frozenset({"Autowired", "Bean"})

TEST_ANNOTATIONS: frozenset[str] = frozenset({"Test", "ParameterizedTest", "RepeatedTest"})

# Mapping annotation -> HTTP method (None means inherit/any for @RequestMapping).
MAPPING_ANNOTATIONS: dict[str, str | None] = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
    "RequestMapping": None,
}


def normalize_annotation(name: str) -> str:
    """Strip a leading ``@`` and any package qualifier from an annotation name."""

    name = name.lstrip("@").strip()
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    return name


def is_stereotype(annotation: str) -> bool:
    return normalize_annotation(annotation) in STEREOTYPE_ANNOTATIONS


def is_test_annotation(annotation: str) -> bool:
    return normalize_annotation(annotation) in TEST_ANNOTATIONS


def mapping_http_method(annotation: str) -> str | None | bool:
    """Return the HTTP method for a mapping annotation.

    Returns the method string ("GET"...), None for @RequestMapping (unspecified),
    or False if the annotation is not a mapping annotation at all.
    """

    norm = normalize_annotation(annotation)
    if norm in MAPPING_ANNOTATIONS:
        return MAPPING_ANNOTATIONS[norm]
    return False

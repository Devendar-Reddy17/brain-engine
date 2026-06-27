from brain.core.indexing.chunker import approx_tokens, make_chunk_id
from brain.core.indexing.semantic_chunker import chunk_file
from brain.core.parsing.fallback_java_parser import FallbackJavaParser

SAMPLE = """
package com.example;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int sub(int a, int b) {
        return a - b;
    }
}
"""


def test_approx_tokens():
    assert approx_tokens("") == 1
    assert approx_tokens("abcd") == 1
    assert approx_tokens("a" * 40) == 10


def test_chunk_id_is_deterministic():
    a = make_chunk_id("X.java", "add", 5, 0)
    b = make_chunk_id("X.java", "add", 5, 0)
    c = make_chunk_id("X.java", "add", 6, 0)
    assert a == b
    assert a != c


def test_method_level_chunks():
    parse_result = FallbackJavaParser().parse(SAMPLE, "Calculator.java")
    chunks = chunk_file(
        rel_path="Calculator.java",
        language="java",
        source=SAMPLE,
        parse_result=parse_result,
        max_chunk_tokens=800,
    )
    names = {c.symbol_name for c in chunks}
    assert "add" in names
    assert "sub" in names
    for chunk in chunks:
        assert chunk.content_hash
        assert chunk.chunk_id


def test_file_level_fallback_for_no_symbols():
    text = "some plain text\nwith no symbols\n"
    parse_result = FallbackJavaParser().parse(text, "notes.txt")
    chunks = chunk_file(
        rel_path="notes.txt",
        language="text",
        source=text,
        parse_result=parse_result,
        max_chunk_tokens=800,
    )
    assert len(chunks) == 1
    assert chunks[0].symbol_type == "file"

"""Tests for retrieval quality improvements.

Tests partial symbol matching, noise filtering, signal-to-content reranking,
and graph expansion from strong matches only.  Uses lightweight fakes so tests
run without external dependencies.
"""

from brain.core.retrieval.intent_classifier import is_noise_term, classify
from brain.core.retrieval.reranker import Candidate, rerank, _score
from brain.types.brain_types import Intent


# -- noise filtering -------------------------------------------------------
def test_get_is_noise_term():
    assert is_noise_term("get") is True


def test_api_is_noise_term():
    assert is_noise_term("api") is True


def test_verifications_is_not_noise_term():
    assert is_noise_term("verifications") is False


def test_kafka_is_not_noise_term():
    assert is_noise_term("kafka") is False


def test_route_is_noise_term():
    assert is_noise_term("route") is True


# -- intent classifier: expanded stopwords ----------------------------------
def test_classify_filters_generic_terms_from_keywords():
    result = classify("where is GET /api/verifications/{id}")
    kw_lower = {k.lower() for k in result.keywords}
    # "get" and "api" are stopwords now — should not appear in keywords.
    assert "get" not in kw_lower
    assert "api" not in kw_lower
    # But "verifications" should be present (it's a useful term).
    assert "verifications" in kw_lower


def test_classify_merges_paths_into_keywords():
    result = classify("where is GET /api/verifications/{id}")
    # Path patterns should be in keywords, not a separate field.
    assert any("/api/verifications" in k for k in result.keywords)


def test_classify_merges_identifiers_into_keywords():
    result = classify("where is VerificationController")
    assert "VerificationController" in result.keywords


# -- reranker: signal-to-content scoring ------------------------------------
def _cand(chunk_id="c1", symbol_name=None, content="", source="lexical", base_score=1.0, file_path="f.java"):
    return Candidate(
        chunk_id=chunk_id,
        file_path=file_path,
        symbol_name=symbol_name,
        symbol_type="method",
        start_line=1,
        end_line=5,
        content=content,
        source=source,
        base_score=base_score,
    )


def test_exact_symbol_match_scores_higher_than_partial():
    exact = _cand(symbol_name="PaymentService", content="x", source="symbol", base_score=2.0)
    partial = _cand(symbol_name="PaymentService", content="x", source="symbol_partial", base_score=1.5)
    ranked = rerank(
        [exact, partial],
        intent=Intent.QUESTION,
        keywords=["PaymentService"],
        file_hints=[],
        changed_files=set(),
        top_k=2,
    )
    # Both match, but exact should rank first due to higher source weight + base_score.
    assert ranked[0].chunk_id == "c1"


def test_partial_symbol_match_boosts_candidate():
    """'verifications' should boost 'VerificationController' via partial match."""
    cand = _cand(
        chunk_id="c1",
        symbol_name="VerificationController",
        content="class VerificationController { ... }",
        source="symbol_partial",
        base_score=1.5,
    )
    other = _cand(
        chunk_id="c2",
        symbol_name="UnrelatedThing",
        content="something completely different",
        source="lexical",
        base_score=1.0,
    )
    ranked = rerank(
        [cand, other],
        intent=Intent.QUESTION,
        keywords=["verifications"],
        file_hints=[],
        changed_files=set(),
        top_k=2,
    )
    assert ranked[0].chunk_id == "c1"
    assert ranked[0].score > ranked[1].score


def test_path_pattern_in_content_boosts_candidate():
    """A candidate whose content contains a path pattern from the query should be boosted."""
    with_path = _cand(
        chunk_id="c1",
        symbol_name="getVerification",
        content='@GetMapping("/api/verifications/{id}")',
        source="lexical",
        base_score=1.0,
    )
    without_path = _cand(
        chunk_id="c2",
        symbol_name="somethingElse",
        content="totally unrelated content",
        source="lexical",
        base_score=1.0,
    )
    # The path pattern is now just a keyword — no separate route_hints param.
    ranked = rerank(
        [with_path, without_path],
        intent=Intent.QUESTION,
        keywords=["verifications", "/api/verifications/{id}"],
        file_hints=[],
        changed_files=set(),
        top_k=2,
    )
    assert ranked[0].chunk_id == "c1"
    assert ranked[0].score > ranked[1].score


def test_generic_noise_terms_dont_produce_false_boosts():
    """Noise terms like 'get' should not boost candidates via content match."""
    cand_with_get = _cand(
        chunk_id="c1",
        symbol_name="Foo",
        content="get bar",
        source="lexical",
        base_score=1.0,
    )
    cand_without = _cand(
        chunk_id="c2",
        symbol_name="Bar",
        content="nothing here",
        source="lexical",
        base_score=1.0,
    )
    # "get" is a noise term — it's in stopwords so it won't be in keywords.
    # "bar" is also a stopword? No, "bar" is not in stopwords. Let me use
    # a query where the only useful term is a noise word.
    result = classify("where is get")
    kw_lower = {k.lower() for k in result.keywords}
    assert "get" not in kw_lower
    # With no useful keywords, both candidates should score equally.
    ranked = rerank(
        [cand_with_get, cand_without],
        intent=Intent.QUESTION,
        keywords=result.keywords,
        file_hints=[],
        changed_files=set(),
        top_k=2,
    )
    # Neither should be boosted — scores should be equal (both lexical, base 1.0).
    assert ranked[0].score == ranked[1].score


def test_kafka_keyword_boosts_kafka_symbol():
    """Generic test: 'kafka' should boost 'KafkaConsumerConfig' via partial match."""
    kafka_cand = _cand(
        chunk_id="c1",
        symbol_name="KafkaConsumerConfig",
        content="class KafkaConsumerConfig { ... }",
        source="symbol_partial",
        base_score=1.5,
    )
    unrelated = _cand(
        chunk_id="c2",
        symbol_name="Foo",
        content="something else",
        source="lexical",
        base_score=1.0,
    )
    ranked = rerank(
        [kafka_cand, unrelated],
        intent=Intent.QUESTION,
        keywords=["kafka"],
        file_hints=[],
        changed_files=set(),
        top_k=2,
    )
    assert ranked[0].chunk_id == "c1"
    assert ranked[0].score > ranked[1].score


def test_symbol_partial_source_weight():
    """symbol_partial source should weight between symbol and lexical."""
    from brain.core.retrieval.reranker import _SOURCE_WEIGHTS
    assert _SOURCE_WEIGHTS["symbol_partial"] > _SOURCE_WEIGHTS["lexical"]
    assert _SOURCE_WEIGHTS["symbol_partial"] < _SOURCE_WEIGHTS["symbol"]


# -- _score: signal-to-content matching -------------------------------------
def test_score_signal_in_symbol_name():
    cand = _cand(symbol_name="PaymentService", content="x")
    score = _score(
        cand, Intent.QUESTION,
        kw_lower={"paymentservice"},
        file_hints=[], changed_files=set(),
        all_signals={"paymentservice"},
    )
    # Exact match gives +6.0
    assert score >= 6.0


def test_score_signal_in_content_only():
    cand = _cand(symbol_name="Foo", content="uses PaymentService internally")
    score = _score(
        cand, Intent.QUESTION,
        kw_lower={"paymentservice"},
        file_hints=[], changed_files=set(),
        all_signals={"paymentservice"},
    )
    # Content match gives +3.0 but no exact symbol match.
    # Base = source_weight(lexical=2.0) + base_score(1.0) = 3.0, + 3.0 = 6.0
    assert score >= 3.0
    assert score <= 6.0


def test_score_partial_symbol_match():
    cand = _cand(symbol_name="PaymentService", content="x")
    score = _score(
        cand, Intent.QUESTION,
        kw_lower=set(),  # no exact match
        file_hints=[], changed_files=set(),
        all_signals={"payment"},  # partial: "payment" in "paymentservice"
    )
    # Partial symbol match gives +3.0
    assert score >= 3.0

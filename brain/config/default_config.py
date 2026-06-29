"""Default configuration model for Local Code Brain.

Mirrors the ``.brain/config.yml`` structure described in the product spec.
Pydantic provides validation and defaults so a missing/partial config still
produces a fully-populated, valid configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BrainSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    repo_root: str = "."


class DaemonSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    host: str = "127.0.0.1"
    port: int = 8765
    auto_start: bool = True
    python_command: str = "python"


class IndexingSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    debounce_ms: int = 2500
    max_cpu_cores: int = 1
    initial_index_parallelism: int = 2
    incremental_index_parallelism: int = 1
    batch_size_files: int = 10
    batch_sleep_ms: int = 250
    pause_when_system_cpu_above: int = 75
    pause_when_memory_above_mb: int = 2048
    pause_during_build: bool = True
    pause_when_on_battery: bool = True


class HashScanSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    enabled: bool = True
    interval_seconds: int = 600
    max_files_per_batch: int = 200
    batch_sleep_ms: int = 500


class EmbeddingSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    provider: str = "mock"
    model: str = "local-code-embedding-small"
    batch_size_chunks: int = 16
    max_chunk_tokens: int = 800
    only_embed_changed_chunks: bool = True
    lazy_load_model: bool = True
    unload_after_idle_minutes: int = 15
    # Optional OpenAI-compatible embedding endpoint
    base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"


class RetrievalSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    max_context_tokens: int = 25000
    lexical_top_k: int = 20
    vector_top_k: int = 30
    symbol_top_k: int = 20
    rerank_top_k: int = 12
    include_tests: bool = True
    include_callers: bool = True
    include_callees: bool = True
    include_config: bool = True
    include_git_diff: bool = True


class AiSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    provider: str = "none"
    base_url: str = ""
    api_key_env: str = ""
    model: str = ""
    temperature: float = 0.1


class ContextVerifierSection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    enabled: bool = False
    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "qwen/qwen3-coder:free"
    api_key_env: str = "OPENROUTER_API_KEY"
    max_attempts: int = 3
    min_confidence: float = 0.75
    explain_with_verifier: bool = True


class ApplySection(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    require_patch_approval: bool = True
    run_tests_after_apply: bool = True
    test_command: str = ""


class BrainConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    brain: BrainSection = Field(default_factory=BrainSection)
    daemon: DaemonSection = Field(default_factory=DaemonSection)
    indexing: IndexingSection = Field(default_factory=IndexingSection)
    hash_scan: HashScanSection = Field(default_factory=HashScanSection)
    embedding: EmbeddingSection = Field(default_factory=EmbeddingSection)
    retrieval: RetrievalSection = Field(default_factory=RetrievalSection)
    ai: AiSection = Field(default_factory=AiSection)
    context_verifier: ContextVerifierSection = Field(default_factory=ContextVerifierSection)
    apply: ApplySection = Field(default_factory=ApplySection)


def default_config() -> BrainConfig:
    """Return a fully-populated default configuration."""

    return BrainConfig()


def default_config_dict() -> dict:
    """Return defaults as a plain dict suitable for YAML serialization."""

    return default_config().model_dump()

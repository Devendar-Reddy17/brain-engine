/** TypeScript view of `.brain/config.yml`. Mirrors the Python BrainConfig. */

export interface BrainConfigShape {
  brain: { repo_root: string };
  daemon: {
    host: string;
    port: number;
    auto_start: boolean;
    python_command: string;
  };
  indexing: {
    debounce_ms: number;
    max_cpu_cores: number;
    initial_index_parallelism: number;
    incremental_index_parallelism: number;
    batch_size_files: number;
    batch_sleep_ms: number;
    pause_when_system_cpu_above: number;
    pause_when_memory_above_mb: number;
    pause_during_build: boolean;
    pause_when_on_battery: boolean;
  };
  hash_scan: {
    enabled: boolean;
    interval_seconds: number;
    max_files_per_batch: number;
    batch_sleep_ms: number;
  };
  embedding: {
    provider: string;
    model: string;
    batch_size_chunks: number;
    max_chunk_tokens: number;
    only_embed_changed_chunks: boolean;
    lazy_load_model: boolean;
    unload_after_idle_minutes: number;
    base_url: string;
    api_key_env: string;
  };
  retrieval: {
    max_context_tokens: number;
    lexical_top_k: number;
    vector_top_k: number;
    symbol_top_k: number;
    rerank_top_k: number;
    include_tests: boolean;
    include_callers: boolean;
    include_callees: boolean;
    include_config: boolean;
    include_git_diff: boolean;
  };
  ai: {
    provider: string;
    base_url: string;
    api_key_env: string;
    model: string;
    temperature: number;
  };
  apply: {
    require_patch_approval: boolean;
    run_tests_after_apply: boolean;
    test_command: string;
  };
}

export function defaultConfig(): BrainConfigShape {
  return {
    brain: { repo_root: "." },
    daemon: {
      host: "127.0.0.1",
      port: 8765,
      auto_start: true,
      python_command: "python",
    },
    indexing: {
      debounce_ms: 2500,
      max_cpu_cores: 1,
      initial_index_parallelism: 2,
      incremental_index_parallelism: 1,
      batch_size_files: 10,
      batch_sleep_ms: 250,
      pause_when_system_cpu_above: 75,
      pause_when_memory_above_mb: 2048,
      pause_during_build: true,
      pause_when_on_battery: true,
    },
    hash_scan: {
      enabled: true,
      interval_seconds: 600,
      max_files_per_batch: 200,
      batch_sleep_ms: 500,
    },
    embedding: {
      provider: "mock",
      model: "local-code-embedding-small",
      batch_size_chunks: 16,
      max_chunk_tokens: 800,
      only_embed_changed_chunks: true,
      lazy_load_model: true,
      unload_after_idle_minutes: 15,
      base_url: "",
      api_key_env: "OPENAI_API_KEY",
    },
    retrieval: {
      max_context_tokens: 25000,
      lexical_top_k: 20,
      vector_top_k: 30,
      symbol_top_k: 20,
      rerank_top_k: 12,
      include_tests: true,
      include_callers: true,
      include_callees: true,
      include_config: true,
      include_git_diff: true,
    },
    ai: {
      provider: "openai-compatible",
      base_url: "",
      api_key_env: "OPENAI_API_KEY",
      model: "gpt-4.1",
      temperature: 0.1,
    },
    apply: {
      require_patch_approval: true,
      run_tests_after_apply: true,
      test_command: "",
    },
  };
}

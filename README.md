# Local Code Brain

A local-first repo intelligence engine that understands a software repository and prepares high-quality, compact context for AI coding agents. It reduces token waste from repeated full-repo scans by keeping repo understanding fresh locally and sending only relevant context to the configured reasoning model when you ask for answers or code changes.

> The local brain is mostly normal software: file watching, git hook detection, hash scanning, tree-sitter parsing, AST/symbol extraction, semantic chunking, dependency-graph building, local embeddings/vector search, SQLite metadata storage, context packing, and patch preview/apply. By default it is context-only and requires no LLM install. Standalone CLI answers can use a hosted OpenAI-compatible gateway, while local Ollama/LM Studio models remain optional.

## Architecture

```
User CLI prompt
  -> TypeScript CLI (apps/cli)
  -> Python brain daemon localhost API (brain/daemon, FastAPI)
  -> Intent classifier -> Context retriever -> SQLite repo brain DB
  -> Context packer -> Token savings estimator
  -> Optional AI provider (hosted or local OpenAI-compatible) [only for standalone ask/edit/review]
  -> Patch preview/apply
```

- **TypeScript** (`apps/cli`, `apps/mcp-server`, `packages/shared`): CLI entry, user commands, patch preview/apply UX, AI provider calls, MCP server.
- **Python** (`brain/`): daemon, indexing, hashing, tree-sitter parsing, symbol extraction, chunking, dependency graph, embeddings/vector search, retrieval/reranking, context packing, SQLite storage.
- **Communication**: CLI talks to the Python daemon over a localhost HTTP API (default `127.0.0.1:8765`). The CLI auto-starts the daemon if it is not running.

## CLI commands

| Command | Purpose |
| --- | --- |
| `brain config` | Generate/update `.brain/config.yml` |
| `brain index` | First-time full index of the repository |
| `brain watch` | Background watch + incremental re-index |
| `brain status` | Repo/index stats and freshness |
| `brain context "<prompt>"` | Show compact context package (no AI call) |
| `brain ask "<prompt>"` | Retrieve context and answer with configured AI, or show compact context when AI is disabled |
| `brain edit "<prompt>"` | Retrieve context + ask AI for a unified diff patch |
| `brain apply <patch>` | Apply an approved patch safely |
| `brain review --diff` | Review current git diff with AI |
| `brain git-refresh` | Reconcile files changed by git operations |

## Getting started

### Python daemon

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

### TypeScript CLI

```bash
npm install
npm run build
npm link
```

### Explanation model

By default, the brain does not call an AI provider:

```yaml
ai:
  provider: none
  base_url: ""
  api_key_env: ""
  model: ""
  temperature: 0.1
```

In this mode, `brain context` and MCP tools return compact, relevant chunks for the AI agent that is already running in Cursor, Windsurf, Copilot, Claude Desktop, or another MCP client. Users do not need to install Ollama or any other local model for MCP usage.

For standalone CLI explanations, configure a hosted OpenAI-compatible gateway that your product or deployment provides:

```yaml
ai:
  provider: hosted
  base_url: https://your-brain-ai-gateway.example.com/v1
  api_key_env: BRAIN_AI_KEY
  model: brain-code
  temperature: 0.1
```

If the gateway does not require per-user authentication, leave `api_key_env` empty. You can also set `BRAIN_AI_BASE_URL` and use `provider: brain-hosted` when the URL should come from the environment.

For offline/private users, a local OpenAI-compatible server is optional:

```yaml
ai:
  provider: ollama
  base_url: http://127.0.0.1:11434/v1
  api_key_env: ""
  model: qwen2.5-coder:7b
  temperature: 0.1
```

Install Ollama separately only if you want this local mode, then pull a code-capable model:

```bash
ollama pull qwen2.5-coder:7b
```

LM Studio or any local OpenAI-compatible server also works:

```yaml
ai:
  provider: lm-studio
  base_url: http://127.0.0.1:1234/v1
  api_key_env: ""
  model: local-model
```

Any other OpenAI-compatible endpoint also works with `ai.provider: openai-compatible`, `ai.base_url`, `ai.model`, and optional `ai.api_key_env`.

Then inside any Java/Spring Boot repo:

```bash
brain config
brain index
brain status
brain context "where is login implemented?"
brain ask "explain the authentication flow"
brain edit "add validation to login endpoint"
brain apply .brain/patches/latest.patch
```

## Token savings

Every retrieval reports estimated token reduction (full-repo tokens vs packed-context tokens), computed locally and offline. No AI APIs are called for token estimation.

## Repository layout

```
apps/cli           TypeScript CLI
apps/mcp-server     MCP server
packages/shared     Shared TS types + API schemas
brain/              Python FastAPI daemon + core intelligence
.brain/             Local runtime data (config.yml, brain.db, patches/)
```

## Privacy

- `brain index` and `brain context` never send code to the cloud.
- With the default `ai.provider: none` config, no code is sent to any AI provider.
- `brain ask`, `brain edit`, and `brain review` send the compact packed context only when an AI provider is explicitly configured.

## License

MIT

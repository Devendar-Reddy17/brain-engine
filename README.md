# Local Code Brain

A local-first repo intelligence engine that understands a software repository and prepares high-quality, compact context for AI coding agents (Claude/GPT). It reduces token waste from repeated full-repo scans by keeping repo understanding fresh locally and sending only relevant context to the cloud model when you ask for answers or code changes.

> The local brain is mostly normal software: file watching, git hook detection, hash scanning, tree-sitter parsing, AST/symbol extraction, semantic chunking, dependency-graph building, local embeddings/vector search, SQLite metadata storage, context packing, and patch preview/apply. Cloud models are used **only** for answer generation and code edits.

## Architecture

```
User CLI prompt
  -> TypeScript CLI (apps/cli)
  -> Python brain daemon localhost API (brain/daemon, FastAPI)
  -> Intent classifier -> Context retriever -> SQLite repo brain DB
  -> Context packer -> Token savings estimator
  -> AI provider (OpenAI-compatible) [only for ask/edit/review]
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
| `brain ask "<prompt>"` | Retrieve context + ask AI for an explanation |
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
- Only `brain ask`, `brain edit`, and `brain review` send the compact packed context to the configured AI provider.

## License

MIT

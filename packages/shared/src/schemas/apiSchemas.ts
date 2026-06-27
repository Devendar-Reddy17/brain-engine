/**
 * HTTP API request/response contracts between the TypeScript CLI/MCP server
 * and the Python FastAPI brain daemon. These mirror the Pydantic models in
 * `brain/daemon/models.py`.
 */

import {
  ContextChunk,
  DependencyContext,
  Intent,
  RelevantFile,
  TargetSymbol,
  TokenSavings,
} from "./brainTypes";

export interface HealthResponse {
  status: "ok";
  version: string;
  repoRoot: string | null;
}

export interface IndexRequest {
  /** Optional explicit repo root; daemon detects when omitted. */
  repoRoot?: string;
  /** When true (default for `brain index`), run a full re-index. */
  full?: boolean;
}

export interface IndexResponse {
  repoRoot: string;
  filesScanned: number;
  filesIndexed: number;
  filesSkipped: number;
  chunksCreated: number;
  symbolsExtracted: number;
  durationMs: number;
  /** True when the index was stale and every file was force-rebuilt. */
  forced: boolean;
  /** Authoritative totals currently in the index (not just this run). */
  totalFiles: number;
  totalChunks: number;
  totalSymbols: number;
}

export interface StatusResponse {
  repoRoot: string;
  indexedFiles: number;
  chunks: number;
  symbols: number;
  lastFullIndexAt: string | null;
  lastIncrementalIndexAt: string | null;
  pendingQueueSize: number;
  currentBranch: string | null;
  fresh: boolean;
  /** True when the index was built by older parser/tagger/chunker/schema versions. */
  stale: boolean;
  /** Human-readable explanation shown to the user when `stale` is true. */
  staleReason: string | null;
}

export interface ContextRequest {
  prompt: string;
  /** Optional override of the auto-classified intent. */
  intent?: Intent;
  /** When true, include the full relevant git diff if within budget (edit/review). */
  includeFullDiff?: boolean;
}

export interface ContextResponse {
  /** The full markdown context package ready to send to an AI provider. */
  markdown: string;
  prompt: string;
  intent: Intent;
  confidence: number;
  confidenceReason: string;
  tokenSavings: TokenSavings;
  relevantFiles: RelevantFile[];
  targetSymbols: TargetSymbol[];
  chunks: ContextChunk[];
  dependencyContext: DependencyContext;
  gitDiffSummary: string | null;
  missingContextWarnings: string[];
}

/**
 * The permanent public ask contract. ALL clients (CLI, MCP, IDE plugins, web)
 * call `/ask`; `/context` is an internal/back-compat detail they must not use.
 */
export interface AskRequest {
  question: string;
  /** Optional repo path; validated against the daemon's repo root. */
  repoPath?: string;
}

/** A single navigable result from a local (non-AI) repository query. */
export interface LocalQueryItem {
  name: string;
  kind: string;
  filePath: string;
  startLine: number;
  endLine: number;
  parentSymbol?: string | null;
  annotations?: string[];
  tags?: string[];
}

/** A group of child symbols sharing the same owner/parent. */
export interface LocalQueryGroup {
  owner: string;
  ownerKind: string;
  ownerFile: string;
  items: LocalQueryItem[];
}

/** Structured answer produced entirely from the local Brain index. */
export interface LocalQueryResult {
  queryType: string;
  title: string;
  count: number;
  items: LocalQueryItem[];
  /** Grouped results (owner → child symbols); present for grouped queries. */
  groups?: LocalQueryGroup[];
  /** Set when the index is stale; results may be incomplete until `brain index`. */
  staleWarning?: string | null;
}

/**
 * Routing result. Clients only need to branch on `executionPath`:
 * - `local`       -> render `result` directly (no AI call).
 * - `ai_required` -> feed `context` to the client's existing AI pipeline.
 */
export interface AskResponse {
  executionPath: "local" | "ai_required";
  result?: LocalQueryResult | null;
  context?: ContextResponse | null;
}

export interface GitRefreshRequest {
  repoRoot?: string;
}

export interface GitRefreshResponse {
  enqueued: number;
  files: string[];
}

export interface EnqueueChangeRequest {
  paths: string[];
  /** Defaults to "modified". */
  eventType?: "created" | "modified" | "deleted" | "renamed";
  /** Higher = processed sooner. Defaults to user-edit priority. */
  priority?: number;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
}

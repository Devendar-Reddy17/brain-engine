/**
 * Core domain types for Local Code Brain, shared between the CLI and MCP server.
 * These mirror the Python Pydantic models in `brain/types/brain_types.py`.
 */

export type Intent =
  | "question"
  | "code_edit"
  | "test_creation"
  | "bug_fix"
  | "refactor"
  | "review"
  | "architecture_explanation";

export type SymbolKind =
  | "class"
  | "interface"
  | "enum"
  | "method"
  | "function"
  | "constructor"
  | "field"
  | "constant"
  | "import"
  | "package"
  | "annotation"
  | "route"
  | "test"
  | "bean"
  | "config";

export type Visibility = "public" | "protected" | "private" | "package" | "unknown";

export type EdgeType =
  | "imports"
  | "calls"
  | "extends"
  | "implements"
  | "references"
  | "tested_by"
  | "configures"
  | "routes_to";

export type ChangeEventType = "created" | "modified" | "deleted" | "renamed";

export interface RelevantFile {
  path: string;
  reason: string;
}

export interface TargetSymbol {
  name: string;
  kind: SymbolKind;
  file: string;
  startLine: number;
  endLine: number;
}

export interface ContextChunk {
  file: string;
  symbol: string | null;
  startLine: number;
  endLine: number;
  reason: string;
  content: string;
}

export interface DependencyContext {
  callers: string[];
  callees: string[];
  interfaces: string[];
  implementations: string[];
  configs: string[];
  routes: string[];
  tests: string[];
}

/** Local, offline token-reduction metrics produced by the retrieval pipeline. */
export interface TokenSavings {
  repoTokens: number;
  contextTokens: number;
  reductionPercentage: number;
}

import type { LocalQueryResult } from "@local-code-brain/shared";

/**
 * Pure formatters for `brain ask` output. Kept free of side effects and color
 * so they are easy to unit test; the command layer adds styling/IO.
 */

export function formatExecutionPath(path: "local" | "ai_required"): string {
  return path === "local" ? "Local Repository Query" : "AI Reasoning";
}

/** Render a local query result as plain text lines (no color, no IO). */
export function formatLocalResult(result: LocalQueryResult): string[] {
  const lines: string[] = [];
  if (result.staleWarning) {
    lines.push(`! ${result.staleWarning}`);
    lines.push("");
  }
  lines.push(`${result.title}: ${result.count}`);
  lines.push("");

  if (result.groups && result.groups.length > 0) {
    for (const group of result.groups) {
      let header = group.owner;
      if (group.ownerKind) {
        header += ` [${group.ownerKind}]`;
      }
      lines.push(header);
      for (const item of group.items) {
        let location = "";
        if (item.filePath && item.startLine) {
          location = ` (${item.filePath}:${item.startLine})`;
        } else if (item.filePath) {
          location = ` (${item.filePath})`;
        }
        lines.push(`  - ${item.name}${location}`);
      }
      lines.push("");
    }
    return lines;
  }

  if (result.items.length === 0) {
    lines.push("(no results)");
    return lines;
  }

  for (const item of result.items) {
    let location = "";
    if (item.filePath && item.startLine) {
      location = ` (${item.filePath}:${item.startLine})`;
    } else if (item.filePath) {
      location = ` (${item.filePath})`;
    }
    lines.push(`- ${item.name}${location}`);
  }
  return lines;
}

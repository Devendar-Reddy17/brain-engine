import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { BrainDaemonClient } from "./client/brainDaemonClient";
import { askRepo, askRepoInputSchema } from "./tools/askRepoTool";
import { getRepoContext, getRepoContextInputSchema } from "./tools/getRepoContextTool";
import { reviewDiff, reviewDiffInputSchema } from "./tools/reviewDiffTool";

function textResult(text: string) {
  return { content: [{ type: "text" as const, text }] };
}

/** Build the MCP server exposing Local Code Brain repo intelligence as tools. */
export function buildServer(client: BrainDaemonClient): Server {
  const server = new Server(
    { name: "local-code-brain", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: "get_repo_context",
        description:
          "Get a compact, dependency-aware context package for a prompt from the local repo brain.",
        inputSchema: getRepoContextInputSchema,
      },
      {
        name: "ask_repo",
        description: "Get repository context framed to answer a question about the codebase.",
        inputSchema: askRepoInputSchema,
      },
      {
        name: "review_diff",
        description:
          "Get repository context plus the current git diff, framed for code review.",
        inputSchema: reviewDiffInputSchema,
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args = {} } = request.params;
    switch (name) {
      case "get_repo_context":
        return textResult(
          await getRepoContext(client, {
            prompt: String((args as Record<string, unknown>).prompt ?? ""),
            includeFullDiff: Boolean((args as Record<string, unknown>).includeFullDiff),
          }),
        );
      case "ask_repo":
        return textResult(
          await askRepo(client, { prompt: String((args as Record<string, unknown>).prompt ?? "") }),
        );
      case "review_diff":
        return textResult(await reviewDiff(client));
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  });

  return server;
}

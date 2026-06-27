#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { BrainDaemonClient } from "./client/brainDaemonClient";
import { buildServer } from "./server";

const HOST = process.env.BRAIN_HOST ?? "127.0.0.1";
const PORT = Number(process.env.BRAIN_PORT ?? "8765");

async function main(): Promise<void> {
  const client = new BrainDaemonClient(HOST, PORT);
  if (!(await client.isAlive())) {
    process.stderr.write(
      `[Brain MCP] Warning: brain daemon not reachable at ${HOST}:${PORT}. ` +
        `Start it with the CLI (e.g. \`brain status\`) or set BRAIN_HOST/BRAIN_PORT.\n`,
    );
  }

  const server = buildServer(client);
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("[Brain MCP] Local Code Brain MCP server running on stdio.\n");
}

void main().catch((err) => {
  process.stderr.write(`[Brain MCP] Fatal: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exitCode = 1;
});

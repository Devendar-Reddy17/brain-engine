import { Command } from "commander";

import { openSession } from "../client/session";
import { printTokenSavings } from "../utils/tokenSavings";

export function registerContextCommand(program: Command): void {
  program
    .command("context")
    .description("Show the compact context package for a prompt (does NOT call AI)")
    .argument("<prompt>", "The user prompt to build context for")
    .option("--full-diff", "Include the full relevant git diff if within budget", false)
    .action(async (prompt: string, opts: { fullDiff?: boolean }) => {
      const { client } = await openSession({ requireConfig: true });
      const res = await client.context({ prompt, includeFullDiff: Boolean(opts.fullDiff) });

      // Context retrieval is local-only: print the package and token savings.
      process.stdout.write(`\n${res.markdown}\n`);
      printTokenSavings(res.tokenSavings);
    });
}

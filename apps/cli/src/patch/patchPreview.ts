import chalk from "chalk";

export interface PatchStats {
  files: string[];
  additions: number;
  deletions: number;
}

const FILE_RE = /^\+\+\+ b\/(.+)$/;

/** Parse a unified diff for a quick summary of touched files and line counts. */
export function summarizePatch(patch: string): PatchStats {
  const files = new Set<string>();
  let additions = 0;
  let deletions = 0;

  for (const line of patch.split("\n")) {
    const m = FILE_RE.exec(line);
    if (m) {
      files.add(m[1]);
      continue;
    }
    if (line.startsWith("+") && !line.startsWith("+++")) {
      additions += 1;
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      deletions += 1;
    }
  }
  return { files: [...files], additions, deletions };
}

/** Render the patch with simple color and a summary footer. */
export function printPatchPreview(patch: string): void {
  for (const line of patch.split("\n")) {
    if (line.startsWith("+") && !line.startsWith("+++")) {
      process.stdout.write(chalk.green(line) + "\n");
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      process.stdout.write(chalk.red(line) + "\n");
    } else if (line.startsWith("@@")) {
      process.stdout.write(chalk.cyan(line) + "\n");
    } else {
      process.stdout.write(chalk.dim(line) + "\n");
    }
  }
  const stats = summarizePatch(patch);
  process.stdout.write(
    `\n${chalk.bold("Patch summary:")} ${stats.files.length} file(s), ` +
      `${chalk.green(`+${stats.additions}`)} / ${chalk.red(`-${stats.deletions}`)}\n`,
  );
}

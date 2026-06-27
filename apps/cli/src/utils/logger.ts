import chalk from "chalk";

/** Minimal logger with a consistent `[Brain]` prefix used across the CLI. */
export const logger = {
  info(message: string): void {
    process.stdout.write(`${message}\n`);
  },
  brain(message: string): void {
    process.stderr.write(`${chalk.cyan("[Brain]")} ${message}\n`);
  },
  success(message: string): void {
    process.stdout.write(`${chalk.green("✓")} ${message}\n`);
  },
  warn(message: string): void {
    process.stderr.write(`${chalk.yellow("!")} ${message}\n`);
  },
  error(message: string): void {
    process.stderr.write(`${chalk.red("✗")} ${message}\n`);
  },
  heading(message: string): void {
    process.stdout.write(`\n${chalk.bold(message)}\n`);
  },
};

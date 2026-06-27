/** Error types for the CLI with user-friendly messages. */

export class BrainCliError extends Error {
  readonly detail?: string;

  constructor(message: string, detail?: string) {
    super(message);
    this.name = "BrainCliError";
    this.detail = detail;
  }
}

export class DaemonUnavailableError extends BrainCliError {
  constructor(message: string, detail?: string) {
    super(message, detail);
    this.name = "DaemonUnavailableError";
  }
}

export class ConfigMissingError extends BrainCliError {
  constructor(message: string, detail?: string) {
    super(message, detail);
    this.name = "ConfigMissingError";
  }
}

export class PatchSafetyError extends BrainCliError {
  constructor(message: string, detail?: string) {
    super(message, detail);
    this.name = "PatchSafetyError";
  }
}

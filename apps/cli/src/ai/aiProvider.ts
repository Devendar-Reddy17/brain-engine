import { BrainConfigShape } from "../config/defaultConfig";
import { BrainCliError } from "../utils/errors";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AiCompletionRequest {
  messages: ChatMessage[];
  temperature?: number;
}

/** Interface for AI providers (local or cloud; only used by ask/edit/review). */
export interface AiProvider {
  readonly model: string;
  complete(req: AiCompletionRequest): Promise<string>;
}

/** Build the configured AI provider. */
export function getAiProvider(config: BrainConfigShape): AiProvider {
  const provider = (config.ai.provider || "openai-compatible").toLowerCase();
  if (!isAiProviderEnabled(config)) {
    throw new BrainCliError(
      "AI provider is disabled.",
      "Set ai.provider to hosted, openai-compatible, ollama, or lm-studio to enable standalone CLI answers.",
    );
  }
  if (
    provider === "openai-compatible" ||
    provider === "openai" ||
    provider === "hosted" ||
    provider === "brain-hosted" ||
    provider === "ollama" ||
    provider === "local" ||
    provider === "local-openai-compatible" ||
    provider === "lm-studio"
  ) {
    // Lazy import to avoid loading the HTTP client for non-AI commands.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
    return new OpenAiCompatibleProvider(config);
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
  return new OpenAiCompatibleProvider(config);
}

export function isAiProviderEnabled(config: BrainConfigShape): boolean {
  const provider = (config.ai.provider || "").toLowerCase();
  return provider !== "" && provider !== "none" && provider !== "disabled" && provider !== "context-only";
}

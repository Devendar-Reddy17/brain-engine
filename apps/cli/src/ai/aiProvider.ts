import { BrainConfigShape } from "../config/defaultConfig";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AiCompletionRequest {
  messages: ChatMessage[];
  temperature?: number;
}

/** Interface for cloud AI providers (only used by ask/edit/review). */
export interface AiProvider {
  readonly model: string;
  complete(req: AiCompletionRequest): Promise<string>;
}

/** Build the configured AI provider. */
export function getAiProvider(config: BrainConfigShape): AiProvider {
  const provider = (config.ai.provider || "openai-compatible").toLowerCase();
  // Only one concrete provider for now; Claude/others slot in here later.
  if (provider === "openai-compatible" || provider === "openai") {
    // Lazy import to avoid loading the HTTP client for non-AI commands.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
    return new OpenAiCompatibleProvider(config);
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
  return new OpenAiCompatibleProvider(config);
}

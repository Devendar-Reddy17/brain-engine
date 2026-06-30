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

export interface AiProviderSettings {
  provider: string;
  base_url: string;
  api_key_env: string;
  model: string;
  temperature: number;
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
    return new OpenAiCompatibleProvider(config, config.ai);
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
  return new OpenAiCompatibleProvider(config, config.ai);
}

export function isAiProviderEnabled(config: BrainConfigShape): boolean {
  const provider = (config.ai.provider || "").toLowerCase();
  return provider !== "" && provider !== "none" && provider !== "disabled" && provider !== "context-only";
}

/** Build the lightweight model used for non-code-generation reasoning. */
export function getReasoningAiProvider(config: BrainConfigShape): AiProvider {
  if (isContextVerifierReasoningEnabled(config)) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { OpenAiCompatibleProvider } = require("./openAiCompatibleProvider");
    return new OpenAiCompatibleProvider(config, {
      provider: config.contextVerifier.provider,
      base_url: config.contextVerifier.baseUrl,
      api_key_env: config.contextVerifier.apiKeyEnv,
      model: config.contextVerifier.model,
      temperature: 0.1,
    });
  }
  return getAiProvider(config);
}

export function isReasoningAiProviderEnabled(config: BrainConfigShape): boolean {
  return isContextVerifierReasoningEnabled(config) || isAiProviderEnabled(config);
}

function isContextVerifierReasoningEnabled(config: BrainConfigShape): boolean {
  const verifier = config.contextVerifier;
  const provider = (verifier?.provider || "").toLowerCase();
  return Boolean(
    verifier?.enabled &&
      provider &&
      provider !== "none" &&
      provider !== "disabled" &&
      verifier.baseUrl &&
      verifier.model,
  );
}

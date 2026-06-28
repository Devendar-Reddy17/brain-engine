import axios from "axios";

import { BrainConfigShape } from "../config/defaultConfig";
import { BrainCliError } from "../utils/errors";
import { AiCompletionRequest, AiProvider } from "./aiProvider";

/** AI provider for any OpenAI-compatible /chat/completions endpoint. */
export class OpenAiCompatibleProvider implements AiProvider {
  readonly model: string;
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly temperature: number;
  private readonly requiresApiKey: boolean;

  constructor(config: BrainConfigShape) {
    const provider = (config.ai.provider || "openai-compatible").toLowerCase();
    const local = isLocalProvider(provider);
    this.model = config.ai.model;
    this.baseUrl = (config.ai.base_url || defaultBaseUrl(provider)).replace(/\/$/, "");
    this.temperature = config.ai.temperature;
    this.requiresApiKey = !local && Boolean(config.ai.api_key_env);
    this.apiKey = config.ai.api_key_env ? (process.env[config.ai.api_key_env] ?? "") : "";
    if (!this.baseUrl) {
      throw new BrainCliError(
        "AI provider base_url is not configured.",
        "Set ai.base_url in .brain/config.yml to your hosted or OpenAI-compatible model gateway.",
      );
    }
    if (!this.model) {
      throw new BrainCliError(
        "AI provider model is not configured.",
        "Set ai.model in .brain/config.yml to the hosted/local model name.",
      );
    }
    if (this.requiresApiKey && !this.apiKey) {
      throw new BrainCliError(
        `AI API key not found in environment variable '${config.ai.api_key_env}'.`,
        `Set it (e.g. $env:${config.ai.api_key_env}="..."), update ai.api_key_env, or clear ai.api_key_env if your gateway does not require auth.`,
      );
    }
  }

  async complete(req: AiCompletionRequest): Promise<string> {
    try {
      const { data } = await axios.post(
        `${this.baseUrl}/chat/completions`,
        {
          model: this.model,
          temperature: req.temperature ?? this.temperature,
          messages: req.messages,
        },
        {
          headers: this.headers(),
          timeout: 300_000,
        },
      );
      const content = data?.choices?.[0]?.message?.content;
      if (typeof content !== "string") {
        throw new BrainCliError("AI provider returned an unexpected response shape.");
      }
      return content;
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail = JSON.stringify(err.response?.data ?? err.message);
        throw new BrainCliError(`AI request failed${status ? ` (HTTP ${status})` : ""}.`, detail);
      }
      throw err;
    }
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }
    return headers;
  }
}

function isLocalProvider(provider: string): boolean {
  return provider === "ollama" || provider === "local" || provider === "local-openai-compatible" || provider === "lm-studio";
}

function defaultBaseUrl(provider: string): string {
  if (provider === "ollama" || provider === "local") {
    return "http://127.0.0.1:11434/v1";
  }
  if (provider === "lm-studio") {
    return "http://127.0.0.1:1234/v1";
  }
  if (provider === "hosted" || provider === "brain-hosted") {
    return process.env.BRAIN_AI_BASE_URL ?? "";
  }
  return "https://api.openai.com/v1";
}

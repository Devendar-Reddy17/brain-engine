import axios from "axios";

import { BrainConfigShape } from "../config/defaultConfig";
import { BrainCliError } from "../utils/errors";
import { AiCompletionRequest, AiProvider, AiProviderSettings } from "./aiProvider";

/** AI provider for any OpenAI-compatible /chat/completions endpoint. */
export class OpenAiCompatibleProvider implements AiProvider {
  readonly model: string;
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly temperature: number;
  private readonly requiresApiKey: boolean;
  private readonly provider: string;

  constructor(config: BrainConfigShape, settings: AiProviderSettings = config.ai) {
    const provider = (settings.provider || "openai-compatible").toLowerCase();
    const local = isLocalProvider(provider);
    this.provider = provider;
    this.model = settings.model;
    this.baseUrl = (settings.base_url || defaultBaseUrl(provider)).replace(/\/$/, "");
    this.temperature = settings.temperature;
    this.requiresApiKey = !local && Boolean(settings.api_key_env);
    this.apiKey = settings.api_key_env ? (process.env[settings.api_key_env] ?? "") : "";
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
        `AI API key not found in environment variable '${settings.api_key_env}'.`,
        `Set it (e.g. $env:${settings.api_key_env}="..."), update the configured api key env, or clear it if your gateway does not require auth.`,
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
    if (this.provider === "openrouter") {
      headers["HTTP-Referer"] = process.env.OPENROUTER_HTTP_REFERER || "https://reposentinel.local";
      headers["X-OpenRouter-Title"] = process.env.OPENROUTER_APP_TITLE || "RepoSentinel Brain";
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
  if (provider === "openrouter") {
    return "https://openrouter.ai/api/v1";
  }
  return "https://api.openai.com/v1";
}

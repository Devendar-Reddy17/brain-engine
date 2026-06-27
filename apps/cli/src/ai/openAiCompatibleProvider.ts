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

  constructor(config: BrainConfigShape) {
    this.model = config.ai.model;
    this.baseUrl = (config.ai.base_url || "https://api.openai.com/v1").replace(/\/$/, "");
    this.temperature = config.ai.temperature;
    this.apiKey = process.env[config.ai.api_key_env] ?? "";
    if (!this.apiKey) {
      throw new BrainCliError(
        `AI API key not found in environment variable '${config.ai.api_key_env}'.`,
        `Set it (e.g. $env:${config.ai.api_key_env}="sk-...") or update ai.api_key_env in .brain/config.yml.`,
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
          headers: {
            Authorization: `Bearer ${this.apiKey}`,
            "Content-Type": "application/json",
          },
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
}

const test = require("node:test");
const assert = require("node:assert");

const { getAiProvider, isAiProviderEnabled } = require("../dist/ai/aiProvider");
const { OpenAiCompatibleProvider } = require("../dist/ai/openAiCompatibleProvider");

function config(ai) {
  return {
    ai: {
      provider: "ollama",
      base_url: "",
      api_key_env: "",
      model: "qwen2.5-coder:7b",
      temperature: 0.1,
      ...ai,
    },
  };
}

test("ollama provider does not require an API key", () => {
  const provider = new OpenAiCompatibleProvider(config({ provider: "ollama" }));
  assert.strictEqual(provider.model, "qwen2.5-coder:7b");
});

test("lm-studio provider does not require an API key", () => {
  const provider = new OpenAiCompatibleProvider(config({ provider: "lm-studio", model: "local-model" }));
  assert.strictEqual(provider.model, "local-model");
});

test("cloud openai-compatible provider still requires an API key", () => {
  const envName = "BRAIN_TEST_EMPTY_OPENAI_KEY";
  delete process.env[envName];
  assert.throws(
    () => new OpenAiCompatibleProvider(config({
      provider: "openai-compatible",
      base_url: "https://api.openai.com/v1",
      api_key_env: envName,
      model: "gpt-4.1",
    })),
    /AI API key not found/,
  );
});

test("disabled provider is reported as not enabled", () => {
  assert.strictEqual(isAiProviderEnabled(config({ provider: "none" })), false);
  assert.throws(() => getAiProvider(config({ provider: "none" })), /AI provider is disabled/);
});

test("hosted provider can use base url without local model install", () => {
  const provider = new OpenAiCompatibleProvider(config({
    provider: "hosted",
    base_url: "https://example.invalid/v1",
    api_key_env: "",
    model: "brain-code",
  }));
  assert.strictEqual(provider.model, "brain-code");
});

test("hosted provider requires a base url", () => {
  assert.throws(
    () => new OpenAiCompatibleProvider(config({
      provider: "hosted",
      base_url: "",
      api_key_env: "",
      model: "brain-code",
    })),
    /base_url is not configured/,
  );
});

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMConfig:
    name: str
    model: str
    role: str
    weight: float
    api_key: Optional[str] = None
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 500
    temperature: float = 0.7
    requests_per_minute: int = 10
    enabled: bool = True

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

# Gunakan satu API key untuk semua (OpenRouter)
OPENROUTER_API_KEY = os.getenv("QWEN_API_KEY", "")

LLM_CONFIGS = {
    "claude": LLMConfig(
        name="Claude Haiku",
        model="anthropic/claude-3-haiku",
        role="risk_analyst",
        weight=0.20,
        api_key=OPENROUTER_API_KEY,
    ),
    "gemini": LLMConfig(
        name="Gemma 2 9B",
        model="google/gemma-2-9b-it:free",
        role="news_analyst",
        weight=0.25,
        api_key=OPENROUTER_API_KEY,
    ),
    "gpt": LLMConfig(
        name="Llama 3.1 8B",
        model="meta-llama/llama-3.1-8b-instruct:free",
        role="pattern_analyst",
        weight=0.20,
        api_key=OPENROUTER_API_KEY,
    ),
    "grok": LLMConfig(
        name="Mistral 7B",
        model="mistralai/mistral-7b-instruct:free",
        role="sentiment_analyst",
        weight=0.15,
        api_key=OPENROUTER_API_KEY,
    ),
    "deepseek": LLMConfig(
        name="DeepSeek R1",
        model="deepseek/deepseek-r1:free",
        role="quant_analyst",
        weight=0.10,
        api_key=OPENROUTER_API_KEY,
    ),
    "qwen": LLMConfig(
        name="Qwen Turbo",
        model="qwen/qwen-turbo",
        role="asia_market_analyst",
        weight=0.10,
        api_key=OPENROUTER_API_KEY,
    ),
}
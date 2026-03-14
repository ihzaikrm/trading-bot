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
        model="anthropic/claude-haiku-4-5",
        role="risk_analyst",
        weight=0.20,
        api_key=OPENROUTER_API_KEY,
    ),
    "gemini": LLMConfig(
        name="Gemma 2 9B",
        model="google/gemini-2.0-flash-001",
        role="news_analyst",
        weight=0.25,
        api_key=OPENROUTER_API_KEY,
    ),
    "gpt": LLMConfig(
        name="Llama 3.1 8B",
        model="openai/gpt-4o-mini",
        role="pattern_analyst",
        weight=0.20,
        api_key=OPENROUTER_API_KEY,
    ),
    "grok": LLMConfig(
        name="Mistral 7B",
        model="x-ai/grok-3-mini",
        role="sentiment_analyst",
        weight=0.15,
        api_key=OPENROUTER_API_KEY,
    ),
    "deepseek": LLMConfig(
        name="DeepSeek R1",
        model="deepseek/deepseek-chat",
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
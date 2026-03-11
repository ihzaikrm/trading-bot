import os
from dataclasses import dataclass
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

@dataclass
class LLMConfig:
    name: str
    api_key: str
    model: str
    base_url: str
    max_tokens: int
    temperature: float
    requests_per_minute: int
    role: str
    weight: float
    enabled: bool = True

    @property
    def is_available(self):
        if not self.api_key: return False
        bad = ["xxxxxxx", "sk-ant-xxx", "AIzaSyx", "xai-xxx"]
        return not any(x in self.api_key for x in bad)

@dataclass
class TradingConfig:
    mode: str = "paper"
    max_daily_loss_pct: float = 3.0
    max_position_size_pct: float = 5.0
    min_confidence: float = 0.65
    min_llm_agreement: int = 3
    cooldown_minutes: int = 15

OR = os.getenv("QWEN_API_KEY", "")

LLM_CONFIGS: Dict[str, LLMConfig] = {

    "claude": LLMConfig(
        name="Claude Haiku (OpenRouter)",
        api_key=OR,
        model="anthropic/claude-haiku-4-5",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=5,
        role="risk_analyst", weight=0.20,
    ),

    "gemini": LLMConfig(
        name="Llama 3.3 70B (Groq)",
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=30,
        role="trend_analyst", weight=0.20,
    ),

    "gpt": LLMConfig(
        name="GPT-4o-mini (OpenRouter)",
        api_key=OR,
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=5,
        role="pattern_analyst", weight=0.20,
    ),

    "grok": LLMConfig(
        name="Grok Beta (OpenRouter)",
        api_key=OR,
        model="x-ai/grok-3-mini",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.4,
        requests_per_minute=5,
        role="sentiment_analyst", weight=0.15,
    ),

    "deepseek": LLMConfig(
        name="DeepSeek V3 (OpenRouter)",
        api_key=OR,
        model="deepseek/deepseek-chat",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.2,
        requests_per_minute=10,
        role="quant_analyst", weight=0.10,
    ),

    "qwen": LLMConfig(
        name="Qwen Turbo (OpenRouter)",
        api_key=OR,
        model="qwen/qwen-turbo",
        base_url="https://openrouter.ai/api/v1",
        max_tokens=1024, temperature=0.3,
        requests_per_minute=10,
        role="asia_market_analyst", weight=0.10,
    ),
}

TRADING = TradingConfig(
    mode=os.getenv("TRADING_MODE", "paper"),
    max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0")),
    max_position_size_pct=float(os.getenv("MAX_POSITION_SIZE_PCT", "5.0")),
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# config/settings.py
# LLM Configuration using OpenRouter (all via QWEN_API_KEY)

LLM_CONFIGS = {
    "claude": {
        "name": "Claude Haiku",
        "model": "anthropic/claude-3-haiku",
        "role": "risk_analyst",
        "weight": 0.20
    },
    "gemini": {
        "name": "Gemma 2 9B",
        "model": "google/gemma-2-9b-it:free",
        "role": "news_analyst",
        "weight": 0.25
    },
    "gpt": {
        "name": "Llama 3.1 8B",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "role": "pattern_analyst",
        "weight": 0.20
    },
    "grok": {
        "name": "Mistral 7B",
        "model": "mistralai/mistral-7b-instruct:free",
        "role": "sentiment_analyst",
        "weight": 0.15
    },
    "deepseek": {
        "name": "DeepSeek R1",
        "model": "deepseek/deepseek-r1:free",
        "role": "quant_analyst",
        "weight": 0.10
    },
    "qwen": {
        "name": "Qwen Turbo",
        "model": "qwen/qwen-turbo",
        "role": "asia_market_analyst",
        "weight": 0.10
    }
}
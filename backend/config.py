import os
import random
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default model for LLM players
DEFAULT_MODEL = "google/gemini-2.0-flash-001"

# Diverse model pool for multi-LLM games
# Format: (model_id, short_label, provider)
# All models tested and verified working with OpenRouter
MODEL_POOL = [
    # Claude models
    ("anthropic/claude-sonnet-4", "Claude4", "Anthropic"),
    
    # OpenAI models
    ("openai/gpt-4o", "GPT4o", "OpenAI"),
    
    # Google models
    ("google/gemini-2.5-flash", "Gem2.5F", "Google"),
]


def get_random_models(count: int) -> list[tuple[str, str, str]]:
    """Get a random selection of models for a game.
    
    Returns list of (model_id, label, provider) tuples.
    Ensures variety by trying to pick from different providers.
    """
    if count >= len(MODEL_POOL):
        # Use all models, shuffle them
        models = MODEL_POOL.copy()
        random.shuffle(models)
        return models[:count]
    
    # Group by provider for variety
    by_provider = {}
    for model in MODEL_POOL:
        provider = model[2]
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(model)
    
    selected = []
    providers = list(by_provider.keys())
    random.shuffle(providers)
    
    # Round-robin selection from providers
    while len(selected) < count:
        for provider in providers:
            if len(selected) >= count:
                break
            available = [m for m in by_provider[provider] if m not in selected]
            if available:
                selected.append(random.choice(available))
    
    random.shuffle(selected)
    return selected

# Server Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Game Configuration
DEFAULT_PLAYER_COUNT = 8
DEFAULT_ROLES = {
    "MAFIA": 2,
    "DETECTIVE": 1,
    "DOCTOR": 1,
    "VILLAGER": 4,
}


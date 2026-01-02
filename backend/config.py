import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default model for LLM players
DEFAULT_MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"

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


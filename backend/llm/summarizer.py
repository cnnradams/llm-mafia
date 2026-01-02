"""Day summarization using LLM."""
from typing import Optional

from game.state import GameState
from llm.openrouter_client import get_client
from llm.prompts import build_summarization_prompt
from config import DEFAULT_MODEL


async def summarize_day(game_state: GameState, day: int, model: str = DEFAULT_MODEL) -> str:
    """Summarize a day's events using LLM."""
    client = get_client()
    
    prompt = build_summarization_prompt(game_state, day)
    
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    try:
        response = await client.chat_completion(model, messages, temperature=0.5)
        summary = response["choices"][0]["message"]["content"]
        return summary.strip()
    except Exception as e:
        # Fallback to basic summary if LLM fails
        return f"Day {day} summary unavailable due to error: {str(e)}"


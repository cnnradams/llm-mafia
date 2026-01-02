"""OpenRouter API client."""
import json
import httpx
import asyncio
from typing import Dict, Any, Optional

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL


class OpenRouterClient:
    """Client for OpenRouter API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
        
        self.base_url = OPENROUTER_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    
    async def chat_completion(
        self,
        model: str,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make a chat completion request with retry logic."""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                if "choices" not in data or not data["choices"]:
                    raise ValueError("Invalid response format from OpenRouter")
                
                return data
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        raise
                else:
                    raise
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)
        
        raise Exception("Failed to get response from OpenRouter after retries")
    
    async def get_json_response(
        self,
        model: str,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Get a JSON response from the LLM."""
        # Add system message to enforce JSON output
        system_message = {
            "role": "system",
            "content": "You must respond with valid JSON only. Do not include any text before or after the JSON."
        }
        messages_with_system = [system_message] + messages
        
        response = await self.chat_completion(model, messages_with_system, temperature)
        
        content = response["choices"][0]["message"]["content"]
        
        # Try to extract JSON from response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Could not parse JSON from response: {content}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global client instance
_client: Optional[OpenRouterClient] = None


def get_client() -> OpenRouterClient:
    """Get or create the global OpenRouter client."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


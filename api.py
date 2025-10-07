"""
api.py - Handles all API calls to OpenRouter and external services
"""

import os
import requests
from typing import Optional, Dict, Any

class OpenRouterAPI:
    """Handles communication with OpenRouter API"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # Using a fast, reliable model (you can change this)
        self.model = "meta-llama/llama-3.1-8b-instruct:free"
    
    def get_ai_response(self, user_message: str) -> Dict[str, Any]:
        """
        Send message to OpenRouter and get AI response
        
        Args:
            user_message: The user's input message
            
        Returns:
            Dict with 'success', 'reply', and optional 'error' keys
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "API key not configured",
                "reply": "Configuration error. Please contact the administrator."
            }
        
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Smooth, a friendly and helpful chatbot. Keep responses concise and engaging."
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Check for rate limiting (429) or quota exceeded
            if response.status_code == 429 or response.status_code == 402:
                return {
                    "success": False,
                    "error": "rate_limit",
                    "reply": "Now I am Sleepy 💤😴 ask Tomorrow"
                }
            
            response.raise_for_status()
            data = response.json()
            
            # Extract the AI's reply
            ai_reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not ai_reply:
                return {
                    "success": False,
                    "error": "empty_response",
                    "reply": "I'm having trouble thinking right now. Try again!"
                }
            
            return {
                "success": True,
                "reply": ai_reply.strip()
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "timeout",
                "reply": "I'm thinking too slow right now. Try again!"
            }
        except requests.exceptions.RequestException as e:
            # Check if it's a rate limit in the exception
            if "429" in str(e) or "quota" in str(e).lower():
                return {
                    "success": False,
                    "error": "rate_limit",
                    "reply": "Now I am Sleepy 💤😴 ask Tomorrow"
                }
            return {
                "success": False,
                "error": str(e),
                "reply": "Something went wrong. Please try again later."
            }


class NewsAPI:
    """Fetches cryptocurrency news headlines"""
    
    @staticmethod
    def get_crypto_news() -> str:
        """
        Fetch latest cryptocurrency news headlines
        
        Returns:
            Formatted string with news headlines
        """
        try:
            # Using CoinGecko's free API (no key required)
            url = "https://api.coingecko.com/api/v3/search/trending"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract trending coins
            trending = data.get("coins", [])[:5]
            
            if not trending:
                return "📰 Crypto News: Markets are moving! Stay updated with your favorite crypto sources."
            
            news_text = "📰 *Trending Cryptocurrencies Today:*\n\n"
            for idx, coin_data in enumerate(trending, 1):
                coin = coin_data.get("item", {})
                name = coin.get("name", "Unknown")
                symbol = coin.get("symbol", "")
                rank = coin.get("market_cap_rank", "N/A")
                news_text += f"{idx}. {name} ({symbol.upper()}) - Rank #{rank}\n"
            
            return news_text
            
        except Exception as e:
            # Fallback message if news fetch fails
            return "📰 Crypto News: Unable to fetch latest headlines. Check CoinGecko or CoinDesk for updates!"
    
    @staticmethod
    def get_motivational_quote() -> str:
        """
        Fetch a motivational quote
        
        Returns:
            Formatted motivational quote
        """
        try:
            # Using ZenQuotes API (free, no key required)
            url = "https://zenquotes.io/api/today"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                quote = data[0].get("q", "")
                author = data[0].get("a", "Unknown")
                return f"💫 *Quote of the Day:*\n\n\"{quote}\"\n\n— {author}"
            
        except Exception:
            pass
        
        # Fallback quotes if API fails
        fallback_quotes = [
            "💫 \"The future belongs to those who believe in the beauty of their dreams.\" — Eleanor Roosevelt",
            "💫 \"Success is not final, failure is not fatal: it is the courage to continue that counts.\" — Winston Churchill",
            "💫 \"Believe you can and you're halfway there.\" — Theodore Roosevelt",
            "💫 \"The only way to do great work is to love what you do.\" — Steve Jobs"
        ]
        
        import random
        return random.choice(fallback_quotes)


# Placeholder for future multimedia support
class MediaAPI:
    """
    Placeholder for future image/multimedia processing
    Can be extended to handle:
    - Image generation
    - Image analysis
    - Audio processing
    - Video processing
    """
    
    @staticmethod
    def process_image(image_url: str) -> Dict[str, Any]:
        """Placeholder for image processing"""
        return {
            "success": False,
            "error": "not_implemented",
            "message": "Image processing coming soon!"
        }
    
    @staticmethod
    def generate_image(prompt: str) -> Dict[str, Any]:
        """Placeholder for image generation"""
        return {
            "success": False,
            "error": "not_implemented",
            "message": "Image generation coming soon!"
        }

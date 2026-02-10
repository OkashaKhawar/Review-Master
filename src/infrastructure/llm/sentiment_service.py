"""
Sentiment Service - LLM-Based Sentiment Classification
=======================================================

ARCHITECTURAL DECISION:
- Uses OpenRouter API for free LLM access (Llama 3.2)
- Falls back to keyword heuristics if no API key
- Returns ONLY: Positive, Neutral, or Negative
- No business logic - just classification

WHY OPENROUTER:
- Free tier available for testing
- Access to multiple models
- Simple API (OpenAI-compatible)

EXTENSIBILITY:
- To use different model: change model in settings
- To use local LLM: add LocalSentimentService class
- To use OpenAI: change API URL and key
"""

import logging
import requests
from enum import Enum
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)


class Sentiment(Enum):
    """
    Sentiment classification result.
    
    DESIGN: Using Enum ensures type safety and prevents
    typos/inconsistencies in sentiment values.
    """
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class SentimentServiceError(Exception):
    """Base exception for sentiment service errors."""
    pass


class SentimentService:
    """
    Sentiment classification service using LLM.
    
    USAGE:
        service = SentimentService()
        result = service.classify("I loved the service!")
        print(result)  # Sentiment.POSITIVE
    
    FALLBACK BEHAVIOR:
    - If no API key: uses keyword heuristics
    - If API fails: uses keyword heuristics
    - If response invalid: defaults to Neutral
    """
    
    # Prompt template for LLM
    PROMPT_TEMPLATE = (
        "Classify the sentiment of the following customer message into "
        "exactly one of: Positive, Neutral, Negative. "
        "Reply with only the single word label. "
        "If unclear or very short, reply Neutral.\n\n"
        "Message: '''{message}'''"
    )
    
    # Keywords for heuristic fallback
    POSITIVE_KEYWORDS = [
        "great", "good", "love", "loved", "excellent", "awesome", 
        "amazing", "happy", "satisfied", "wonderful", "fantastic",
        "perfect", "best", "thank", "thanks", "appreciate"
    ]
    
    NEGATIVE_KEYWORDS = [
        "bad", "terrible", "disappoint", "disappointed", "poor", 
        "hate", "unhappy", "problem", "issue", "worst", "awful",
        "horrible", "never", "waste", "refund", "angry", "upset"
    ]
    
    def __init__(self):
        """Initialize sentiment service with settings."""
        settings = get_settings()
        self._api_key = settings.llm.api_key
        self._api_url = settings.llm.api_url
        self._model = settings.llm.model
        self._temperature = settings.llm.temperature
        self._timeout = settings.llm.timeout_seconds
        
        if not self._api_key:
            logger.warning(
                "No OPENROUTER_API_KEY set. "
                "Sentiment analysis will use keyword heuristics."
            )
    
    def classify(self, text: str) -> Sentiment:
        """
        Classify sentiment of text.
        
        Args:
            text: Customer message text.
            
        Returns:
            Sentiment enum value.
        """
        # Handle empty/short text
        if not text or len(text.strip()) < 3:
            logger.debug("Text too short, defaulting to Neutral")
            return Sentiment.NEUTRAL
        
        # Try LLM if API key available
        if self._api_key:
            result = self._classify_with_llm(text)
            if result:
                return result
        
        # Fallback to heuristics
        return self._classify_with_heuristics(text)
    
    def _classify_with_llm(self, text: str) -> Optional[Sentiment]:
        """
        Classify using OpenRouter LLM API.
        
        Returns:
            Sentiment or None if API call fails.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/reviewmaster",  # Required by OpenRouter
        }
        
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": self.PROMPT_TEMPLATE.format(message=text)
                }
            ],
            "temperature": self._temperature,
            "max_tokens": 10,  # We only need one word
        }
        
        try:
            response = requests.post(
                self._api_url,
                headers=headers,
                json=payload,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            data = response.json()
            content = self._extract_response_content(data)
            
            return self._parse_sentiment_label(content)
            
        except requests.Timeout:
            logger.warning("LLM API timeout, falling back to heuristics")
            return None
            
        except requests.RequestException as e:
            logger.warning(f"LLM API error: {e}, falling back to heuristics")
            return None
            
        except Exception as e:
            logger.exception(f"Unexpected error in LLM call: {e}")
            return None
    
    def _extract_response_content(self, data: dict) -> str:
        """Extract text content from API response."""
        try:
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                return message.get("content", "").strip()
        except (KeyError, IndexError, TypeError):
            pass
        return ""
    
    def _parse_sentiment_label(self, content: str) -> Optional[Sentiment]:
        """Parse LLM response into Sentiment enum."""
        if not content:
            return None
        
        # Extract first word and normalize
        first_word = content.split()[0].strip().capitalize()
        
        # Map to enum
        sentiment_map = {
            "Positive": Sentiment.POSITIVE,
            "Neutral": Sentiment.NEUTRAL,
            "Negative": Sentiment.NEGATIVE,
        }
        
        result = sentiment_map.get(first_word)
        
        if result is None:
            logger.warning(f"Unexpected LLM label: {first_word}, defaulting to Neutral")
            return Sentiment.NEUTRAL
        
        logger.debug(f"LLM classified as: {result.value}")
        return result
    
    def _classify_with_heuristics(self, text: str) -> Sentiment:
        """
        Fallback classification using keyword matching.
        
        Simple but effective for obvious cases.
        """
        lower_text = text.lower()
        
        has_positive = any(kw in lower_text for kw in self.POSITIVE_KEYWORDS)
        has_negative = any(kw in lower_text for kw in self.NEGATIVE_KEYWORDS)
        
        if has_positive and not has_negative:
            logger.debug("Heuristic: Positive (keywords found)")
            return Sentiment.POSITIVE
        
        if has_negative and not has_positive:
            logger.debug("Heuristic: Negative (keywords found)")
            return Sentiment.NEGATIVE
        
        logger.debug("Heuristic: Neutral (mixed or no keywords)")
        return Sentiment.NEUTRAL

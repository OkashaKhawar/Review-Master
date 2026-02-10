"""
Settings Module - Centralized Configuration Management
=======================================================

ARCHITECTURAL DECISION:
- All configuration is loaded from environment variables (no hardcoded secrets)
- Settings are immutable dataclass for safety and clarity
- Single source of truth for all configurable values

EXTENSIBILITY:
- To add database support: add connection string settings
- To switch LLM provider: add provider-specific API settings
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from functools import lru_cache

# Load .env file if present (development convenience)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


@dataclass(frozen=True)
class WhatsAppSettings:
    """WhatsApp safety and automation settings."""
    
    # SAFETY: Rate limits to avoid WhatsApp blocking
    max_messages_per_hour: int = 10
    max_messages_per_day: int = 50
    
    # SAFETY: Human-like delay ranges (in seconds)
    min_delay_between_messages: int = 40
    max_delay_between_messages: int = 120
    
    # SAFETY: Wait time for customer reply (seconds per poll, max polls)
    reply_poll_interval: int = 30
    reply_max_polls: int = 20  # 10 minutes total
    
    # Browser settings
    headless: bool = False  # MUST be False for QR code scanning
    

@dataclass(frozen=True)
class LLMSettings:
    """OpenRouter LLM settings for sentiment analysis."""
    
    api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    
    # Free model from OpenRouter
    model: str = "meta-llama/llama-3.2-3b-instruct:free"
    
    # Deterministic output
    temperature: float = 0.0
    timeout_seconds: int = 15


@dataclass(frozen=True)
class ReviewSettings:
    """Review flow settings."""
    
    google_review_link: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_REVIEW_LINK",
            "https://search.google.com/local/writereview?placeid=YOUR_PLACE_ID"
        )
    )


@dataclass(frozen=True)
class Settings:
    """
    Root settings container - Single source of truth for all configuration.
    
    Usage:
        from src.infrastructure.config import get_settings
        settings = get_settings()
        print(settings.llm.api_key)
    """
    
    # Sub-settings groups
    whatsapp: WhatsAppSettings = field(default_factory=WhatsAppSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    review: ReviewSettings = field(default_factory=ReviewSettings)
    
    # File paths
    customers_file: Path = field(
        default_factory=lambda: Path(os.getenv("CUSTOMERS_FILE", "customers.xlsx"))
    )
    
    def validate(self) -> list[str]:
        """
        Validate settings and return list of warnings/errors.
        Returns empty list if all settings are valid.
        """
        issues = []
        
        if not self.llm.api_key:
            issues.append(
                "WARNING: OPENROUTER_API_KEY not set. "
                "Sentiment analysis will use keyword fallback."
            )
        
        if "YOUR_PLACE_ID" in self.review.google_review_link:
            issues.append(
                "WARNING: GOOGLE_REVIEW_LINK contains placeholder. "
                "Set your actual Google Place ID."
            )
        
        if not self.customers_file.exists():
            issues.append(
                f"WARNING: Customers file not found: {self.customers_file}. "
                "A template will be created."
            )
        
        return issues


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get singleton Settings instance.
    Cached to ensure consistent settings throughout application lifecycle.
    """
    return Settings()

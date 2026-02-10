"""
Messaging Provider - Abstraction Layer for WhatsApp Messaging
==============================================================

Provides a unified interface for sending WhatsApp messages.
Currently supports Selenium-based automation. Ready for WhatsApp Cloud API.

USAGE:
    # Selenium (current)
    provider = SeleniumProvider()
    provider.connect()
    provider.send_message("923001234567", "Hello!")

    # Future API (swap with minimal changes)
    provider = APIProvider(api_key="your-key", phone_number_id="12345")
    provider.connect()
    provider.send_message("923001234567", "Hello!")
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class MessagingProvider(ABC):
    """
    Abstract base class for WhatsApp messaging providers.
    Implement this interface to add new messaging backends.
    """

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Connect to the messaging service. Returns True if successful."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if provider is currently connected and ready."""
        ...

    @abstractmethod
    def send_message(self, phone: str, text: str) -> bool:
        """Send a text message to a phone number. Returns True if sent."""
        ...

    @abstractmethod
    def wait_for_reply(self, phone: str, timeout: int = 180) -> Optional[str]:
        """Wait for an incoming reply. Returns message text or None."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        ...


class SeleniumProvider(MessagingProvider):
    """
    Selenium-based WhatsApp Web automation.
    Wraps the existing WhatsAppClient for backward compatibility.
    """

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._client = None
        self._connected = False

    def connect(self, **kwargs) -> bool:
        """Launch browser and open WhatsApp Web."""
        try:
            from .whatsapp_client import WhatsAppClient
            self._client = WhatsAppClient(headless=self._headless)
            return True
        except Exception as e:
            logger.exception(f"Failed to launch Selenium WhatsApp: {e}")
            return False

    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def confirm_login(self, timeout: int = 30) -> bool:
        """Wait for QR code scan and confirm login."""
        if not self._client:
            return False
        result = self._client.wait_for_login(timeout=timeout)
        self._connected = result
        return result

    def send_message(self, phone: str, text: str) -> bool:
        """Open chat and send message via Selenium."""
        if not self._client:
            return False
        if not self._client.open_chat(phone):
            return False
        return self._client.send_message(text)

    def wait_for_reply(self, phone: str, timeout: int = 180) -> Optional[str]:
        """Wait for reply in the currently open chat."""
        if not self._client:
            return None
        return self._client.wait_for_reply(timeout=timeout, poll_interval=3)

    def read_latest_incoming(self) -> Optional[str]:
        """Read latest incoming message in current chat."""
        if not self._client:
            return None
        return self._client.read_latest_incoming_message()

    @property
    def raw_client(self):
        """Access the underlying WhatsAppClient (for advanced Selenium usage)."""
        return self._client

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._connected = False


class APIProvider(MessagingProvider):
    """
    WhatsApp Cloud API / third-party API provider (stub).

    TODO: Implement when API key is available.

    Configuration needed:
        - api_key: Your WhatsApp Business API key
        - phone_number_id: Your registered WhatsApp phone number ID
        - api_url: API endpoint (default: Meta Cloud API)

    Example future usage:
        provider = APIProvider(
            api_key="EAAxxxxxxx",
            phone_number_id="1234567890",
        )
        provider.connect()
        provider.send_message("923001234567", "Hello!")
    """

    # Meta WhatsApp Cloud API base URL
    DEFAULT_API_URL = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        api_key: str = "",
        phone_number_id: str = "",
        api_url: str = "",
    ):
        self._api_key = api_key
        self._phone_number_id = phone_number_id
        self._api_url = api_url or self.DEFAULT_API_URL
        self._connected = False

    def connect(self, **kwargs) -> bool:
        """Verify API credentials are valid."""
        if not self._api_key or not self._phone_number_id:
            logger.error("APIProvider: api_key and phone_number_id are required")
            return False

        # TODO: Make a test API call to verify credentials
        # response = requests.get(
        #     f"{self._api_url}/{self._phone_number_id}",
        #     headers={"Authorization": f"Bearer {self._api_key}"}
        # )
        # self._connected = response.ok

        logger.warning("APIProvider: connect() is a stub — implement API verification")
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    def send_message(self, phone: str, text: str) -> bool:
        """
        Send message via WhatsApp Cloud API.

        TODO: Implement actual API call:
            POST {api_url}/{phone_number_id}/messages
            Headers: Authorization: Bearer {api_key}
            Body: {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": text}
            }
        """
        if not self._connected:
            logger.error("APIProvider: not connected")
            return False

        # TODO: Replace with actual implementation
        # import requests
        # response = requests.post(
        #     f"{self._api_url}/{self._phone_number_id}/messages",
        #     headers={
        #         "Authorization": f"Bearer {self._api_key}",
        #         "Content-Type": "application/json",
        #     },
        #     json={
        #         "messaging_product": "whatsapp",
        #         "to": phone,
        #         "type": "text",
        #         "text": {"body": text},
        #     },
        # )
        # return response.ok

        logger.warning(f"APIProvider: send_message() stub called for {phone}")
        return False

    def wait_for_reply(self, phone: str, timeout: int = 180) -> Optional[str]:
        """
        Wait for reply via webhook (not polling).

        NOTE: WhatsApp Cloud API uses webhooks for incoming messages.
        This method would need a different approach — likely checking
        a local queue/database that a webhook endpoint populates.

        TODO: Implement webhook-based reply listening
        """
        logger.warning("APIProvider: wait_for_reply() stub — implement webhook listener")
        return None

    def close(self) -> None:
        self._connected = False
        logger.info("APIProvider: closed")

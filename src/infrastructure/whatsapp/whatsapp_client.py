"""
WhatsApp Client - Selenium-Based WhatsApp Web Automation
=========================================================
"""

import logging
import time
import random
from typing import Optional, List, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

from ..config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppClientError(Exception):
    """Base exception for WhatsApp client errors."""
    pass


class WhatsAppBlockedError(WhatsAppClientError):
    """Raised when WhatsApp shows blocking/warning indicators."""
    pass


class WhatsAppClient:
    """
    Selenium-based WhatsApp Web client.
    """
    
    # UPDATED CSS Selectors - WhatsApp Web 2024/2025
    # These use more robust attribute-based selectors
    SELECTORS = {
        "search_box": 'div[contenteditable="true"][data-tab="3"]',
        "message_input": 'div[contenteditable="true"][data-tab="10"]',
        "message_input_alt": 'footer div[contenteditable="true"]',
        
        # Message containers - using data attributes which are more stable
        "all_messages": 'div[data-pre-plain-text]',
        "message_text_primary": 'span.selectable-text.copyable-text',
        "message_text_alt": 'span[dir="ltr"]',
        "message_text_fallback": 'span.selectable-text',
        
        # Alternative message container selectors
        "message_row": 'div[data-id]',
        "chat_container": 'div[data-tab="8"]',
    }
    
    BLOCK_INDICATORS = [
        "temporarily banned",
        "account is temporarily",
        "verify your phone",
        "unusual activity",
    ]
    
    def __init__(self, headless: bool = False):
        settings = get_settings()
        self._settings = settings.whatsapp
        self._last_read_message_id = None
        
        self.driver = self._create_driver(headless)
        self._navigate_to_whatsapp()
        
    def _create_driver(self, headless: bool) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver."""
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument("--headless=new")
            logger.warning("Running headless - QR code scanning won't work!")
        else:
            options.add_argument("--start-maximized")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        import os
        profile_dir = os.path.join(os.getcwd(), "whatsapp_profile")
        options.add_argument(f"--user-data-dir={profile_dir}")
        logger.info(f"Using Chrome profile at: {profile_dir}")
        
        if ChromeDriverManager:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        else:
            return webdriver.Chrome(options=options)
    
    def _navigate_to_whatsapp(self) -> None:
        """Navigate to WhatsApp Web."""
        self.driver.get("https://web.whatsapp.com/")
        logger.info("Opened WhatsApp Web - please scan QR code if needed")
    
    def _random_delay(self, min_s: float = 0.5, max_s: float = 2.0) -> None:
        """Add human-like random delay."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
    
    def _check_for_blocks(self) -> bool:
        """Check page for blocking/warning indicators."""
        try:
            page_text = self.driver.page_source.lower()
            for indicator in self.BLOCK_INDICATORS:
                if indicator.lower() in page_text:
                    logger.error(f"Block indicator detected: {indicator}")
                    return True
            return False
        except Exception:
            return False
    
    def wait_for_login(self, timeout: int = 120) -> bool:
        """Wait for user to scan QR code and WhatsApp to load."""
        logger.info(f"Waiting up to {timeout}s for QR code scan...")
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.SELECTORS["search_box"])
                )
            )
            logger.info("WhatsApp Web loaded successfully")
            return True
        except TimeoutException:
            logger.error("Timeout waiting for WhatsApp login")
            return False
    
    def open_chat(self, phone: str) -> bool:
        """Open chat with a phone number."""
        if self._check_for_blocks():
            raise WhatsAppBlockedError("WhatsApp blocking detected")
        
        try:
            logger.debug(f"Opening chat with: {phone}")
            
            search_box = self._find_search_box()
            if not search_box:
                return False
            
            search_box.click()
            self._random_delay(0.3, 0.7)
            search_box.send_keys(Keys.CONTROL + "a")
            search_box.send_keys(Keys.BACKSPACE)
            self._random_delay(0.3, 0.5)
            
            for char in phone:
                search_box.send_keys(char)
                self._random_delay(0.05, 0.15)
            
            time.sleep(2)
            search_box.send_keys(Keys.ENTER)
            time.sleep(3)
            
            # Verify chat opened
            if self._find_message_input():
                logger.info(f"Chat opened successfully: {phone}")
                return True
            else:
                logger.warning(f"Could not verify chat opened for: {phone}")
                return False
                
        except Exception as e:
            logger.exception(f"Failed to open chat: {e}")
            return False
    
    def _find_search_box(self):
        """Find the search box element."""
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, self.SELECTORS["search_box"]
            )
        except NoSuchElementException:
            try:
                elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 'div[contenteditable="true"]'
                )
                if elements:
                    return elements[0]
            except Exception:
                pass
            return None
    
    def _find_message_input(self):
        """Find the message input box with multiple fallback selectors."""
        selectors_to_try = [
            self.SELECTORS["message_input"],
            self.SELECTORS["message_input_alt"],
            'div[contenteditable="true"][data-tab="10"]',
            'footer div[contenteditable="true"][data-tab="10"]',
            'div[title="Type a message"]',
        ]
        
        for selector in selectors_to_try:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return element
            except NoSuchElementException:
                continue
        
        return None
    
    def send_message(self, text: str) -> bool:
        """Send a message in the current chat."""
        try:
            self._random_delay(0.5, 1.0)
            
            input_box = self._find_message_input()
            if not input_box:
                logger.error("Could not find message input box")
                return False
            
            input_box.click()
            self._random_delay(0.3, 0.6)
            
            chunk_size = 50
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                input_box.send_keys(chunk)
                self._random_delay(0.1, 0.3)
            
            self._random_delay(0.3, 0.5)
            input_box.send_keys(Keys.ENTER)
            
            logger.info(f"Sent message: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to send message: {e}")
            return False
    
    def _get_message_elements(self) -> List:
        """
        Get all message elements using multiple selector strategies.
        Returns list of tuples: (element, is_incoming, message_id)
        """
        messages = []
        
        # Strategy 1: Use data-pre-plain-text attribute (most reliable)
        try:
            elements = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[data-pre-plain-text]'
            )
            for el in elements:
                try:
                    pre_text = el.get_attribute('data-pre-plain-text') or ''
                    # Incoming messages typically don't have "You" in the timestamp
                    is_incoming = 'You' not in pre_text and '] You:' not in pre_text
                    msg_id = el.get_attribute('data-id') or str(hash(pre_text))
                    messages.append((el, is_incoming, msg_id))
                except StaleElementReferenceException:
                    continue
            if messages:
                return messages
        except Exception as e:
            logger.debug(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Use data-id attribute on message rows
        try:
            elements = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[data-id^="true_"]'  # Incoming
            )
            for el in elements:
                try:
                    msg_id = el.get_attribute('data-id')
                    messages.append((el, True, msg_id))
                except StaleElementReferenceException:
                    continue
            
            elements = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[data-id^="false_"]'  # Outgoing
            )
            for el in elements:
                try:
                    msg_id = el.get_attribute('data-id')
                    messages.append((el, False, msg_id))
                except StaleElementReferenceException:
                    continue
            
            if messages:
                # Sort by position in DOM
                return messages
        except Exception as e:
            logger.debug(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Look for message bubbles by class patterns
        try:
            # Find the conversation pane first
            pane = self.driver.find_element(
                By.CSS_SELECTOR, 'div[data-tab="8"]'
            )
            # Look for focusable message divs
            elements = pane.find_elements(
                By.CSS_SELECTOR, 'div[tabindex="-1"][class*="message"]'
            )
            for idx, el in enumerate(elements):
                try:
                    class_attr = el.get_attribute('class') or ''
                    is_incoming = 'message-in' in class_attr
                    messages.append((el, is_incoming, str(idx)))
                except StaleElementReferenceException:
                    continue
            if messages:
                return messages
        except Exception as e:
            logger.debug(f"Strategy 3 failed: {e}")
        
        return messages
    
    def _extract_text_from_message(self, element) -> Optional[str]:
        """Extract text content from a message element."""
        text_selectors = [
            'span.selectable-text.copyable-text > span',
            'span.selectable-text.copyable-text',
            'span.selectable-text > span',
            'span.selectable-text',
            'span[dir="ltr"]',
            'span.copyable-text',
        ]
        
        for selector in text_selectors:
            try:
                text_elements = element.find_elements(By.CSS_SELECTOR, selector)
                if text_elements:
                    # Get the innermost text
                    for text_el in text_elements:
                        text = text_el.text.strip()
                        if text:
                            return text
            except (NoSuchElementException, StaleElementReferenceException):
                continue
        
        # Fallback: try to get any text content
        try:
            return element.text.strip() if element.text else None
        except:
            return None
    
    def read_latest_message(self) -> Optional[str]:
        """Read the latest message in the current chat."""
        try:
            self._random_delay(0.5, 1.0)
            
            messages = self._get_message_elements()
            
            if not messages:
                logger.debug("No messages found")
                return None
            
            # Get the last message
            element, is_incoming, msg_id = messages[-1]
            text = self._extract_text_from_message(element)
            
            if text:
                logger.debug(f"Latest message ({'incoming' if is_incoming else 'outgoing'}): {text[:50]}")
            
            return text
            
        except Exception as e:
            logger.exception(f"Failed to read messages: {e}")
            return None
    
    def read_latest_incoming_message(self) -> Optional[str]:
        """Read the latest INCOMING message (from customer)."""
        try:
            self._random_delay(0.5, 1.0)
            
            messages = self._get_message_elements()
            
            if not messages:
                logger.debug("No messages found")
                return None
            
            # Filter to incoming only and get the last one
            incoming_messages = [(el, is_in, mid) for el, is_in, mid in messages if is_in]
            
            if not incoming_messages:
                logger.debug("No incoming messages found")
                return None
            
            element, _, msg_id = incoming_messages[-1]
            text = self._extract_text_from_message(element)
            
            if text:
                logger.debug(f"Latest incoming message: {text[:50]}")
            
            return text
            
        except Exception as e:
            logger.exception(f"Failed to read incoming messages: {e}")
            return None
    
    def wait_for_reply(
        self, 
        timeout: int = 180,
        poll_interval: int = 2,
        ignore_text: Optional[str] = None
    ) -> Optional[str]:
        """Wait for an incoming reply from customer."""
        logger.info(f"Waiting up to {timeout}s for reply...")
        start_time = time.time()
        
        # Get current incoming messages to establish baseline
        baseline_messages = set()
        try:
            messages = self._get_message_elements()
            for el, is_in, msg_id in messages:
                if is_in:
                    baseline_messages.add(msg_id)
        except Exception:
            pass
        
        while (time.time() - start_time) < timeout:
            try:
                messages = self._get_message_elements()
                
                if not messages:
                    time.sleep(poll_interval)
                    continue
                
                # Look for new incoming messages
                for element, is_incoming, msg_id in reversed(messages):
                    if not is_incoming:
                        continue
                    
                    # Check if this is a new message
                    if msg_id in baseline_messages:
                        continue
                    
                    text = self._extract_text_from_message(element)
                    
                    if not text:
                        continue
                    
                    if ignore_text and text == ignore_text:
                        continue
                    
                    logger.info(f"Reply received: {text[:50]}...")
                    return text
                
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.debug(f"Error checking for reply: {e}")
                time.sleep(poll_interval)
        
        logger.info("Timeout waiting for reply")
        return None
    
    def debug_dump_messages(self) -> None:
        """Debug helper: dump all found messages to log."""
        logger.info("=== DEBUG: Dumping all messages ===")
        
        messages = self._get_message_elements()
        logger.info(f"Found {len(messages)} message elements")
        
        for i, (el, is_in, msg_id) in enumerate(messages):
            text = self._extract_text_from_message(el)
            direction = "IN" if is_in else "OUT"
            logger.info(f"  [{i}] {direction}: {text[:80] if text else '(no text)'}")
        
        logger.info("=== END DEBUG ===")
    
    def debug_dump_selectors(self) -> None:
        """Debug helper: test which selectors find elements."""
        logger.info("=== DEBUG: Testing selectors ===")
        
        test_selectors = [
            'div[data-pre-plain-text]',
            'div[data-id^="true_"]',
            'div[data-id^="false_"]',
            'span.selectable-text',
            'span.selectable-text.copyable-text',
            'span[dir="ltr"]',
            'div.message-in',
            'div.message-out',
            'div[data-tab="8"]',
            'div[class*="message"]',
        ]
        
        for selector in test_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"  '{selector}': {len(elements)} elements")
            except Exception as e:
                logger.info(f"  '{selector}': ERROR - {e}")
        
        logger.info("=== END DEBUG ===")
    
    def close(self) -> None:
        """Close browser and cleanup."""
        try:
            self.driver.quit()
            logger.info("Browser closed")
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")
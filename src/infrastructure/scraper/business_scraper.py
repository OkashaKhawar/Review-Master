"""
Google Maps Business Scraper
===========================

Scrapes business information (reviews, rating, location, contact) from a Google Maps/Search link.
"""

import logging
import time
import re
from typing import Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

logger = logging.getLogger(__name__)


class BusinessScraper:
    """Scraper for Google Business Profile information."""

    def __init__(self):
        pass

    def _create_driver(self) -> webdriver.Chrome:
        """Create headless Chrome driver."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # User agent to avoid blocking
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        if ChromeDriverManager:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        else:
            return webdriver.Chrome(options=options)

    def scrape(self, url: str) -> Dict[str, str]:
        """
        Scrape business info from the given URL.
        Returns a dictionary with keys: total_reviews, rating, location, contact_info.
        """
        driver = self._create_driver()
        result = {
            "total_reviews": "N/A",
            "rating": "N/A",
            "location": "N/A",
            "contact_info": "N/A"
        }

        try:
            logger.info(f"Scraping URL: {url}")
            driver.get(url)
            
            # Wait for main content to load
            try:
                # Wait for any typical Google Maps element
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for page load")

            # Allow some dynamic content to settle
            time.sleep(3)

            # --- Extract Rating ---
            try:
                # Look for the large rating number (e.g., "4.7")
                # Common classes: fontDisplayLarge, or aria-label on stars
                rating_el = driver.find_element(By.XPATH, "//div[contains(@class, 'fontDisplayLarge')]")
                result["rating"] = rating_el.text.strip()
            except NoSuchElementException:
                # Fallback: try aria-label on star icon
                try:
                    stars = driver.find_element(By.CSS_SELECTOR, "span[role='img'][aria-label*='stars']")
                    val = stars.get_attribute("aria-label").split(" ")[0]
                    result["rating"] = val
                except:
                    pass

            # --- Extract Reviews ---
            try:
                # 1. Try to find the specific "N reviews" or "(N)" pattern
                # Start with the button usually used for reviews
                reviews_el = None
                
                # Strategy A: Look for user-provided span with role="img" and aria-label containing "reviews"
                try:
                    # User provided: <span role="img" aria-label="779 reviews">(779)</span>
                    reviews_el = driver.find_element(By.CSS_SELECTOR, "span[role='img'][aria-label*='reviews']")
                except NoSuchElementException:
                    try:
                        # Fallback: specific selector provided previously: <div class="fontBodySmall">779 reviews</div>
                        reviews_el = driver.find_element(By.CSS_SELECTOR, "div.fontBodySmall")
                        if "reviews" not in reviews_el.text.lower():
                            reviews_el = driver.find_element(By.XPATH, "//div[contains(@class, 'fontBodySmall') and contains(text(), 'reviews')]")
                    except NoSuchElementException:
                        try:
                            # Strategy B: Look for text that looks like "(779)" next to stars
                            reviews_el = driver.find_element(By.XPATH, "//*[contains(text(), '(') and contains(text(), ')')]")
                        except:
                            pass
                
                if reviews_el:
                    text = reviews_el.text.strip() or reviews_el.get_attribute("aria-label")
                    
                    # Extract digits
                    # Cases: "779 reviews", "(779)", "1,234 reviews"
                    # Regex to find number (with commas)
                    match = re.search(r'[\(\s]?([\d,]+)[\)\s]?(?:reviews|review)?', text, re.IGNORECASE)
                    if match:
                        result["total_reviews"] = match.group(1)
                    else:
                        result["total_reviews"] = text 
                else:
                    # Fallback Strategy C: Brute force search for brackets with numbers near rating
                    # This is aggressive but might catch the specific case user mentioned
                    els = driver.find_elements(By.XPATH, "//*[matches(text(), '^\([\d,]+\)$')]") # XPath 2.0 not supported usually in Selenium standard, stick to simple
                    pass

            except Exception as e:
                logger.debug(f"Review extraction failed: {e}")

            # --- Extract Location/Address ---
            try:
                # Look for button with data-item-id="address"
                addr_btn = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
                result["location"] = addr_btn.get_attribute("aria-label").replace("Address: ", "").strip()
            except NoSuchElementException:
                pass

            # --- Extract Phone ---
            try:
                # Look for button with data-item-id="phone"
                phone_btn = driver.find_element(By.CSS_SELECTOR, "button[data-item-id^='phone']")
                result["contact_info"] = phone_btn.get_attribute("aria-label").replace("Phone: ", "").strip()
            except NoSuchElementException:
                pass
            
            logger.info(f"Scraped info: {result}")

        except Exception as e:
            logger.exception(f"Error scraping business info: {e}")
        finally:
            try:
                driver.quit()
            except:
                pass
        
        return result

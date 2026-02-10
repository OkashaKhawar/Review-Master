"""
Campaign Runner - WhatsApp Review Collection
=============================================

Runs the WhatsApp campaign for pending customers.
Start the web UI first, then run this script.

Uses the messaging provider abstraction for flexibility:
- Currently: Selenium-based WhatsApp Web automation
- Future: WhatsApp Cloud API (swap SeleniumProvider for APIProvider)
"""

import sys
import time
import random
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.persistence import Database
from src.infrastructure.whatsapp import SeleniumProvider
from src.infrastructure.llm import SentimentService
from src.infrastructure.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Message Templates ──────────────────────────────────────────
REVIEW_REQUEST = "Hi {name}, we noticed you recently purchased {product}. We hope you're satisfied! Would you mind sharing a quick review about your experience?"
GOOGLE_LINK_MSG = "Thank you so much for your kind words, {name}! We really appreciate it. If you have a moment, we would be grateful if you could share your experience on Google: {link}"
THANK_YOU_MSG = "Thank you for your feedback, {name}. We appreciate you taking the time to share your thoughts with us."


def random_delay(min_s: int = 40, max_s: int = 120):
    """Human-like delay between messages."""
    delay = random.randint(min_s, max_s)
    logger.info(f"Waiting {delay}s before next action...")
    time.sleep(delay)


def run_campaign():
    """Run the review collection campaign."""

    print("\n" + "=" * 60)
    print("   Review Master - Campaign Runner")
    print("=" * 60 + "\n")

    # Initialize
    settings = get_settings()
    db = Database()
    db.init()
    sentiment_service = SentimentService()
    google_link = settings.review.google_review_link

    # Get pending customers (all users — campaign is global)
    pending = db.get_pending_customers()
    if not pending:
        print("No pending customers. All done!")
        return

    print(f"Found {len(pending)} pending customers\n")

    # Launch WhatsApp via Selenium provider
    print("Launching WhatsApp Web...")
    print("   Please scan QR code with your phone.\n")

    provider = SeleniumProvider(headless=False)
    if not provider.connect():
        print("Failed to launch browser")
        return

    print("=" * 60)
    print("SCAN THE QR CODE NOW")
    print("   Wait for chats to load, then press ENTER")
    print("=" * 60)

    try:
        input("\n>>> Press ENTER when WhatsApp is ready... <<<\n")
    except KeyboardInterrupt:
        print("\nCancelled")
        provider.close()
        return

    if not provider.confirm_login(timeout=30):
        print("WhatsApp didn't load. Try again.")
        provider.close()
        return

    print("\nWhatsApp ready! Starting campaign...\n")

    # Process each customer
    for customer in pending:
        print(f"\n{'─' * 40}")
        print(f"Processing: {customer.name} ({customer.phone})")

        try:
            product_name = customer.product or "your recent purchase"

            if customer.has_review:
                # Customer already has review - read and analyze
                print("   Reading existing review...")
                msg = provider.raw_client.read_latest_incoming_message() if provider.raw_client else None

                if msg:
                    llm_sentiment = sentiment_service.classify(msg)
                    sentiment = llm_sentiment.value
                    print(f"   Sentiment: {sentiment}")

                    if sentiment == "Positive":
                        text = GOOGLE_LINK_MSG.format(name=customer.name, link=google_link)
                        print("   Sending Google review link...")
                    else:
                        text = THANK_YOU_MSG.format(name=customer.name)
                        print("   Sending thank you...")

                    if provider.send_message(customer.phone, text):
                        db.mark_done(customer.id, sentiment, text[:100])
                        print("   Done!")
                    else:
                        db.mark_error(customer.id, "Failed to send message")
                        print("   Send failed")
                else:
                    print("   Could not read message")
            else:
                # New customer - request review
                text = REVIEW_REQUEST.format(name=customer.name, product=product_name)
                print(f"   Requesting review...")

                if provider.send_message(customer.phone, text):
                    print("   Waiting for reply (up to 5 min)...")
                    reply = provider.wait_for_reply(customer.phone, timeout=300)

                    if reply:
                        print(f"   Got reply: {reply[:50]}...")
                        llm_sentiment = sentiment_service.classify(reply)
                        sentiment = llm_sentiment.value
                        print(f"   Sentiment: {sentiment}")

                        if sentiment == "Positive":
                            response = GOOGLE_LINK_MSG.format(name=customer.name, link=google_link)
                        else:
                            response = THANK_YOU_MSG.format(name=customer.name)

                        if provider.send_message(customer.phone, response):
                            db.mark_done(customer.id, sentiment, response[:100])
                            print("   Done!")
                        else:
                            db.mark_error(customer.id, "Failed to send response")
                    else:
                        print("   No reply received")
                        db.mark_no_reply(customer.id)
                else:
                    db.mark_error(customer.id, "Failed to send request")
                    print("   Send failed")

            # Delay between customers
            if customer != pending[-1]:
                random_delay(40, 90)

        except KeyboardInterrupt:
            print("\n\nInterrupted! Progress saved.")
            break
        except Exception as e:
            logger.exception(f"Error processing {customer.name}: {e}")
            db.mark_error(customer.id, str(e)[:100])

    # Summary
    print("\n" + "=" * 60)
    print("Campaign Complete!")
    stats = db.get_stats()
    print(f"   Total: {stats['total']} | Done: {stats['done']} | Positive: {stats['positive']}")
    print("=" * 60 + "\n")

    provider.close()


if __name__ == "__main__":
    run_campaign()

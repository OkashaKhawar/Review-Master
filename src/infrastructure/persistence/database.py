"""
SQLite Database Repository - Customer Data Persistence
=======================================================

Stores customers per-user so each business owner only sees their own data.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DATABASE_FILE = "reviewharvest.db"


class CustomerStatus(Enum):
    """Processing status for a customer."""
    PENDING = "pending"
    DONE = "done"
    NO_REPLY = "no_reply"
    ERROR = "error"


@dataclass
class Customer:
    """Customer record from database."""
    id: int
    user_id: int
    name: str
    phone: str
    product: str = ""
    has_review: bool = False
    status: str = "pending"
    sentiment: str = ""
    last_message: str = ""
    created_at: str = ""

    @property
    def is_completed(self) -> bool:
        return self.status == "done"

    @property
    def needs_review_request(self) -> bool:
        return not self.has_review and self.status == "pending"


@dataclass
class User:
    """User (Business Owner) record."""
    id: int
    email: str
    username: str
    business_name: str
    business_link: str
    password_hash: str
    total_reviews: str = "0"
    rating: str = "0.0"
    location: str = ""
    contact_info: str = ""
    created_at: str = ""


class Database:
    """
    SQLite database for Review Master.

    Usage:
        db = Database()
        db.init()

        # Add customer for a specific user
        db.add_customer(user_id=1, name="Sayyam", phone="923401423393")

        # Get pending customers for a user
        pending = db.get_pending_customers(user_id=1)
    """

    def __init__(self, db_path: str = DATABASE_FILE):
        self.db_path = db_path

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    product TEXT DEFAULT '',
                    has_review INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    sentiment TEXT DEFAULT '',
                    last_message TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, phone)
                )
            """)

            # Migrations for older databases
            self._migrate_customers_table(conn)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    business_name TEXT NOT NULL,
                    business_link TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    total_reviews TEXT DEFAULT '0',
                    rating TEXT DEFAULT '0.0',
                    location TEXT DEFAULT '',
                    contact_info TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            logger.info(f"Database initialized: {self.db_path}")

    def _migrate_customers_table(self, conn):
        """Add missing columns to existing customers table."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()}

        migrations = {
            "product": "ALTER TABLE customers ADD COLUMN product TEXT DEFAULT ''",
            "user_id": "ALTER TABLE customers ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0",
        }

        for col, sql in migrations.items():
            if col not in existing:
                try:
                    conn.execute(sql)
                    logger.info(f"Migrated: added '{col}' column to customers")
                except sqlite3.OperationalError:
                    pass

    # ── Customer CRUD ──────────────────────────────────────────────

    def add_customer(self, user_id: int, name: str, phone: str, product: str = "") -> Optional[int]:
        """Add a new customer for a specific user."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO customers (user_id, name, phone, product) VALUES (?, ?, ?, ?)",
                    (user_id, name, phone, product)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Customer with phone {phone} already exists for user {user_id}")
            return None

    def bulk_add_customers(self, user_id: int, customers: list) -> dict:
        """
        Add multiple customers at once for a specific user.

        Args:
            user_id: Owner user ID
            customers: List of dicts with 'name', 'phone', 'product' keys

        Returns:
            Dict with 'added', 'skipped', 'errors' counts
        """
        result = {'added': 0, 'skipped': 0, 'errors': []}

        with self._get_connection() as conn:
            for customer in customers:
                try:
                    name = customer.get('name', '').strip()
                    phone = customer.get('phone', '').strip()
                    product = customer.get('product', '').strip()

                    if not name or not phone:
                        result['errors'].append(f"Missing name or phone: {customer}")
                        continue

                    conn.execute(
                        "INSERT INTO customers (user_id, name, phone, product) VALUES (?, ?, ?, ?)",
                        (user_id, name, phone, product)
                    )
                    result['added'] += 1
                except sqlite3.IntegrityError:
                    result['skipped'] += 1
                except Exception as e:
                    result['errors'].append(f"{customer.get('name', 'Unknown')}: {str(e)}")

        logger.info(f"Bulk import for user {user_id}: {result['added']} added, {result['skipped']} skipped")
        return result

    def get_all_customers(self, user_id: Optional[int] = None) -> List[Customer]:
        """Get all customers, optionally filtered by user."""
        with self._get_connection() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT * FROM customers WHERE user_id = ? ORDER BY id", (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM customers ORDER BY id").fetchall()
            return [self._row_to_customer(row) for row in rows]

    def get_recent_customers(self, user_id: int, limit: int = 4) -> List[Customer]:
        """Get the most recently added customers for a user (for dashboard preview)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM customers WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [self._row_to_customer(row) for row in rows]

    def get_pending_customers(self, user_id: Optional[int] = None) -> List[Customer]:
        """Get customers pending processing."""
        with self._get_connection() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT * FROM customers WHERE user_id = ? AND status = 'pending' ORDER BY id",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM customers WHERE status = 'pending' ORDER BY id"
                ).fetchall()
            return [self._row_to_customer(row) for row in rows]

    def get_customer(self, customer_id: int) -> Optional[Customer]:
        """Get customer by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            return self._row_to_customer(row) if row else None

    def update_customer(self, customer_id: int, **updates) -> bool:
        """Update customer fields."""
        if not updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [customer_id]

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE customers SET {set_clause} WHERE id = ?",
                values
            )
            return True

    def mark_done(self, customer_id: int, sentiment: str = "", last_message: str = ""):
        """Mark customer as processed."""
        self.update_customer(
            customer_id,
            status="done",
            has_review=1,
            sentiment=sentiment,
            last_message=last_message[:200]
        )

    def mark_no_reply(self, customer_id: int):
        """Mark customer as not replying."""
        self.update_customer(customer_id, status="no_reply")

    def mark_error(self, customer_id: int, error: str = ""):
        """Mark customer as having error."""
        self.update_customer(customer_id, status="error", last_message=f"Error: {error}"[:200])

    def delete_customer(self, customer_id: int) -> bool:
        """Delete a customer."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            return True

    def reset_customer(self, customer_id: int):
        """Reset customer to pending status."""
        self.update_customer(
            customer_id,
            status="pending",
            has_review=0,
            sentiment="",
            last_message=""
        )

    def get_stats(self, user_id: Optional[int] = None) -> dict:
        """Get processing statistics, optionally per-user."""
        with self._get_connection() as conn:
            where = "WHERE user_id = ?" if user_id is not None else ""
            params = (user_id,) if user_id is not None else ()

            total = conn.execute(f"SELECT COUNT(*) FROM customers {where}", params).fetchone()[0]
            done = conn.execute(f"SELECT COUNT(*) FROM customers {where} {'AND' if where else 'WHERE'} status='done'",
                                params).fetchone()[0]
            pending = conn.execute(f"SELECT COUNT(*) FROM customers {where} {'AND' if where else 'WHERE'} status='pending'",
                                   params).fetchone()[0]
            no_reply = conn.execute(f"SELECT COUNT(*) FROM customers {where} {'AND' if where else 'WHERE'} status='no_reply'",
                                    params).fetchone()[0]
            positive = conn.execute(f"SELECT COUNT(*) FROM customers {where} {'AND' if where else 'WHERE'} sentiment='Positive'",
                                    params).fetchone()[0]

            return {
                "total": total,
                "done": done,
                "pending": pending,
                "no_reply": no_reply,
                "positive": positive,
                "conversion_rate": round(positive / done * 100, 1) if done > 0 else 0
            }

    def _row_to_customer(self, row: sqlite3.Row) -> Customer:
        """Convert database row to Customer object."""
        try:
            product = row["product"] or ""
        except (KeyError, IndexError):
            product = ""

        try:
            user_id = row["user_id"]
        except (KeyError, IndexError):
            user_id = 0

        return Customer(
            id=row["id"],
            user_id=user_id,
            name=row["name"],
            phone=row["phone"],
            product=product,
            has_review=bool(row["has_review"]),
            status=row["status"],
            sentiment=row["sentiment"] or "",
            last_message=row["last_message"] or "",
            created_at=row["created_at"] or ""
        )

    # ── User CRUD ──────────────────────────────────────────────────

    def create_user(self, email, username, business_name, business_link, password_hash) -> Optional[int]:
        """Create a new user."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO users (email, username, business_name, business_link, password_hash)
                       VALUES (?, ?, ?, ?, ?)""",
                    (email, username, business_name, business_link, password_hash)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return self._row_to_user(row) if row else None

    def get_user_by_email_or_username(self, identifier: str) -> Optional[User]:
        """Get user by email or username (for login)."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ? OR username = ?",
                (identifier, identifier)
            ).fetchone()
            return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row) if row else None

    def update_user_analytics(self, user_id: int, total_reviews: str, rating: str, location: str, contact_info: str):
        """Update user analytics data."""
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE users
                   SET total_reviews = ?, rating = ?, location = ?, contact_info = ?
                   WHERE id = ?""",
                (total_reviews, rating, location, contact_info, user_id)
            )

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert database row to User object."""
        return User(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            business_name=row["business_name"],
            business_link=row["business_link"],
            password_hash=row["password_hash"],
            total_reviews=row["total_reviews"] or "0",
            rating=row["rating"] or "0.0",
            location=row["location"] or "",
            contact_info=row["contact_info"] or "",
            created_at=row["created_at"] or ""
        )


# Quick init helper
def init_with_test_data():
    """Initialize database (no test data inserted by default)."""
    db = Database()
    db.init()
    logger.info("Database initialized")
    return db


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = init_with_test_data()
    print(f"Customers: {db.get_all_customers()}")
    print(f"Stats: {db.get_stats()}")

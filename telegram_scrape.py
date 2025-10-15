import os
import re
import json
import asyncio
import mysql.connector
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from telethon.tl.functions.channels import JoinChannelRequest
from mysql.connector import Error

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

CHANNELS = [
    "https://t.me/InnovegicMart",
    "https://t.me/kenstazon",
    "https://t.me/vrajenterprise16",
    "https://t.me/holidaysg",
    "https://t.me/Onlinemart9",
    "https://t.me/vedantastore",
    "https://t.me/valamji",
    "https://t.me/paramfashion",
    "https://t.me/metrozone",
]

client = OpenAI(api_key=OPENAI_KEY)


class DatabaseHandler:
    """Handles database operations for product storage."""

    def __init__(self):
        self.connection: Optional[mysql.connector.MySQLConnection] = None
        self.connect()
        self.create_table()

    def connect(self) -> None:
        try:
            if self.connection:
                try:
                    self.connection.ping(reconnect=True, attempts=3, delay=2)
                    return
                except Exception:
                    pass

            self.connection = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=True,
            )
            print("✅ Connected to Live DB")
        except Error as e:
            print(f"❌ Error connecting to Live DB: {e}")
            self.connection = None

    def create_table(self) -> None:
        if not self.connection:
            return

        query = """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(500),
            product_description LONGTEXT,
            product_price DECIMAL(10,2),
            channel_name VARCHAR(255),
            message_id BIGINT,
            timestamp DATETIME,
            media_url TEXT,
            source_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
            print("✅ Products table created successfully")
        except Error as e:
            print(f"❌ Error creating table: {e}")

    def insert_product(self, product: dict) -> bool:
        try:
            if not self.connection or not self.connection.is_connected():
                print("🔄 MySQL connection lost — reconnecting...")
                self.connect()
        except Exception as e:
            print(f"⚠️ MySQL connection check failed ({e}), reconnecting...")
            self.connect()

        if not self.connection or not self.connection.is_connected():
            print("❌ MySQL Connection not available even after reconnect.")
            return False

        if is_spammy_text(product.get("product_name", "")) or is_spammy_text(
            product.get("product_description", "")
        ):
            print("🚫 Ignored spammy product message.")
            return False

        price_source = f"{product.get('product_name', '')} {product.get('product_description', '')}"
        price_raw = str(price_source).strip()

        price_match = re.search(
            r"(?:₹|Rs\.?|INR)\s?(\d+(?:\.\d{1,2})?)", price_raw, re.IGNORECASE
        )

        if price_match:
            product_price = round(float(price_match.group(1)), 2)
        else:
            try:
                product_price = round(float(product.get("product_price", 0)), 2)
            except (ValueError, TypeError):
                product_price = 0.00

        query = """
        INSERT INTO products (
            product_name, product_description, product_price, channel_name,
            message_id, timestamp, media_url, source_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            product_name = VALUES(product_name),
            product_description = VALUES(product_description),
            product_price = VALUES(product_price),
            media_url = VALUES(media_url),
            source_type = VALUES(source_type)
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        product.get("product_name", "").strip(),
                        product.get("product_description", "").strip(),
                        product_price,
                        product.get("channel_name", "").strip(),
                        product.get("message_id", 0),
                        product.get("timestamp", datetime.now(timezone.utc)),
                        product.get("media_url", "").strip(),
                        product.get("source_type", "telegram").strip(),
                    ),
                )
            self.connection.commit()
            print(
                f"✅ Product inserted successfully: {product.get('product_name', '')} | Price: {product_price}"
            )
            return True

        except mysql.connector.Error as e:
            if e.errno in (2006, 2013):
                print(
                    f"⚠️ MySQL connection dropped during insert ({e.errno}). Retrying..."
                )
                self.connect()
                return self.insert_product(product)
            else:
                print(f"❌ Error inserting product: {e}")
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                return False

        except Exception as e:
            print(f"❌ Unexpected error during insert: {e}")
            return False


def is_spammy_text(text: str, product_price: str = "0") -> bool:
    text = (text or "").strip()
    if not text:
        return False

    spam_keywords = {
        "join",
        "order now",
        "buy now",
        "click here",
        "telegram",
        "whatsapp",
        "offer",
        "catalogue",
        "link",
    }
    if any(kw in text.lower() for kw in spam_keywords):
        return True

    if product_price != "0":
        return False

    alnum_ratio = len(re.findall(r"[A-Za-z0-9]", text)) / max(len(text), 1)
    special_ratio = len(re.findall(r"[^\w\s]", text)) / max(len(text), 1)
    return len(text) < 3 and alnum_ratio < 0.5 or special_ratio > 0.7


def clean_description(lines: list[str]) -> str:
    skip_patterns = [
        r"^\(?[A-Z]+\)?$",
        r"Available✅+",
        r"In Stock",
        r"Out of Stock",
        r"❌.*?❌",
        r"^\s*[✅🔥💥]+\s*$",
        r"^\(?[A-Za-z]{1,2}\)?$",
    ]

    valid_lines = []
    for line in map(str.strip, lines):
        if not line:
            continue
        line = re.sub(r"\bSZ[-\s]?\d{1,6}\b", "", line, flags=re.IGNORECASE).strip()
        if not line or any(re.match(pat, line, re.IGNORECASE) for pat in skip_patterns):
            continue
        if len(line.split()) >= 2:
            valid_lines.append(line)
    return " ".join(valid_lines)


def clean_message(text: str) -> str:
    text = re.sub(r"https?://\S+|\d{6,12}", "", text)
    for pat in [
        r"✅Avalaible",
        r"Avalaible",
        r"Available",
        r"✅ single price",
        r"🟢.*?PRICE.*?🟢",
        r"Join To (Whatsapp|Telegram) Community.*",
    ]:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    return re.sub(r"\n+", "\n", text).strip()


def extract_price(text: str) -> str:
    """Extract a numeric product price from text."""
    clean_text = text.replace(",", " ").replace("\n", " ")

    patterns = [
        r"(?i)(?:₹|rs\.?|inr|price|rate)\s*[:\-]?\s*(\d+(?:\.\d{1,2})?)",
        r"(?i)(\d+(?:\.\d{1,2})?)\s*(₹|rs\.?|inr|price|rate)",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean_text)
        if match:
            return match.group(1)

    clean_text = re.sub(r"\+?\b91\d{7,10}\b", "", clean_text)
    clean_text = re.sub(
        r"\b\d+\s*(cm|pcs|piece|pair|inch|set|kg|g|ml|ltr|litre|size)\b",
        "",
        clean_text,
        flags=re.I,
    )
    candidates = [
        num
        for num in re.findall(r"\b\d+(?:\.\d{1,2})?\b", clean_text)
        if 1 < float(num) < 9999
    ]

    return candidates[-1] if candidates else "0"


def analyze_message(text: str, channel_name: str) -> dict:
    text = clean_message(text)
    if not text:
        return {
            "product_name": "",
            "product_description": "",
            "product_price": "0",
            "channel_name": channel_name.lower(),
        }

    product_price = extract_price(text)
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", product_price):
        product_price = "0"

    code_match = re.search(r"\b(SZ[-\s]?\d{1,6}|SIZE\s*\d+)\b", text, re.I)
    product_code = (
        (code_match.group(1).strip().upper().replace(" ", "-")) if code_match else ""
    )

    cleaned_text = re.sub(r"\bSZ[-\s]?\d{1,6}\b|\bSIZE\s*\d+\b", "", text, flags=re.I)
    if product_price != "0":
        cleaned_text = re.sub(
            r"\b{}\b".format(re.escape(product_price)), "", cleaned_text
        )

    spam_phrases = [
        "SINGLE PRICE",
        "MAKE THE ORDER",
        "✅",
        "Contact",
        "WhatsApp",
        "Join",
        "Telegram",
        "Click here",
        "Catalogue",
        "Order Now",
        "Shop Now",
        "Limited Stock",
        "Offer",
    ]
    for phrase in spam_phrases:
        cleaned_text = re.sub(re.escape(phrase), "", cleaned_text, flags=re.I)
    cleaned_text = re.sub(r"\n+", "\n", cleaned_text).strip()

    if is_spammy_text(cleaned_text, product_price):
        return {
            "product_name": "",
            "product_description": "",
            "product_price": "0",
            "channel_name": channel_name.lower(),
        }

    lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
    product_name = lines[0] if lines else ""
    product_description = clean_description(lines[1:]) if len(lines) > 1 else ""

    prompt = f"""
        Extract product_name and product_description from the Telegram message.
        Rules:
        - If a product code like "SZ-123" appears, INCLUDE it at the end of the product_name
        (e.g. "Windshield Sunshade SZ-457"). Prefer putting product codes in product_name.
        - product_description should contain only descriptive words (color, size, material, features).
        - If only product name and code are present, set product_description to empty string.
        - Return ONLY a JSON object with keys: product_name, product_description.
        Message: {cleaned_text}
        """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(re.search(r"\{.*\}", content, re.S).group())
        product_name = parsed.get("product_name", product_name).strip()
        product_description = parsed.get(
            "product_description", product_description
        ).strip()
    except Exception as e:
        print(f"❌ OpenAI error: {e}")

    if product_code and product_code.upper() not in product_name.upper():
        if not product_description or len(product_description.split()) <= 2:
            product_name = f"{product_name} {product_code}".strip()
            product_description = ""
        else:
            product_description = re.sub(
                re.escape(product_code), "", product_description, flags=re.I
            ).strip()
            product_name = f"{product_name} {product_code}".strip()

    product_name = re.sub(r"\s{2,}", " ", product_name).strip()
    product_description = re.sub(r"\s{2,}", " ", product_description).strip()

    return {
        "product_name": product_name,
        "product_description": product_description,
        "product_price": (
            re.search(r"\d+", product_price or "0").group()
            if re.search(r"\d+", product_price or "0")
            else "0"
        ),
        "channel_name": channel_name.lower(),
    }


def channel_username_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


async def scrape_past_week(
    tg_client: TelegramClient, db: DatabaseHandler, days: int = 7
) -> None:
    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    os.makedirs("downloads", exist_ok=True)

    for channel in CHANNELS:
        username = channel_username_from_url(channel)
        print(f"\n🔎 Backfilling channel: {username} since {since_date.isoformat()}")

        async for msg in tg_client.iter_messages(username, limit=None):
            if not msg.date or msg.date < since_date:
                break
            if not (msg.message or "").strip() or (
                msg.media and not isinstance(msg.media, MessageMediaPhoto)
            ):
                continue

            extracted = analyze_message(msg.message, username)
            if not extracted["product_name"] and not extracted["product_description"]:
                continue

            product = {
                **extracted,
                "message_id": msg.id,
                "timestamp": msg.date,
                "media_url": "",
                "source_type": "telegram",
            }

            if isinstance(msg.media, MessageMediaPhoto):
                try:
                    file_path = os.path.join("downloads", f"photo_{msg.id}.jpg")
                    await msg.download_media(file=file_path)
                    product["media_url"] = file_path
                except Exception as e:
                    print(f"❌ Error downloading media: {e}")

            db.insert_product(product)


def register_realtime_handlers(tg_client: TelegramClient, db: DatabaseHandler) -> None:
    usernames = [channel_username_from_url(c) for c in CHANNELS]

    @tg_client.on(events.NewMessage(chats=usernames))
    async def handler(event):
        try:
            message = event.message
            chan = getattr(event.chat, "username", None) or getattr(
                event.chat, "id", ""
            )
            chan = channel_username_from_url(str(chan)) if chan else usernames[0]

            if not (message.message or "").strip() or (
                message.media and not isinstance(message.media, MessageMediaPhoto)
            ):
                return

            extracted = analyze_message(message.message, chan)
            if not extracted["product_name"] and (
                not extracted["product_description"]
                or extracted["product_price"] == "0"
            ):
                return

            product = {
                **extracted,
                "message_id": message.id,
                "timestamp": message.date,
                "media_url": "",
                "source_type": "telegram",
            }

            if isinstance(message.media, MessageMediaPhoto):
                try:
                    product["media_url"] = await message.download_media(
                        file="downloads/"
                    )
                except Exception as e:
                    print(f"❌ Error downloading media: {e}")

            db.insert_product(product)
            print(
                f"🟢 New product from {chan}: {product['product_name']} | ₹{product['product_price']}"
            )

        except Exception as e:
            print(f"❌ Error in realtime handler: {e}")


async def scrape_channels() -> None:
    os.makedirs("downloads", exist_ok=True)

    db = DatabaseHandler()
    tg_client = TelegramClient("scraper", API_ID, API_HASH)
    await tg_client.start()

    usernames = [channel_username_from_url(c) for c in CHANNELS]

    for username in usernames:
        try:
            await tg_client(JoinChannelRequest(username))
            print(f"✅ Joined channel: {username}")
        except Exception as e:
            print(f"⚠️ Could not join or already joined channel {username}: {e}")

    print("\n⏳ Fetching messages from the past 7 days...\n")
    await scrape_past_week(tg_client, db, days=7)
    print("\n✅ Completed past week data backfill.\n")

    register_realtime_handlers(tg_client, db)
    print("▶️ Real-time monitoring started for channels:", usernames)

    try:
        await tg_client.run_until_disconnected()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("🛑 Stopping scraper...")

    db.close()
    await tg_client.disconnect()


if __name__ == "__main__":
    asyncio.run(scrape_channels())

import os
import asyncio
from openai import OpenAI
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
import mysql.connector
from mysql.connector import Error
from typing import Optional
from datetime import datetime
import json
import re

API_ID = int(os.getenv("TG_API_ID", "27202419"))
API_HASH = os.getenv("TG_API_HASH", "ec209ef81368e2df05ec34fadc5ec19b")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Root@2111")
DB_NAME = os.getenv("DB_NAME", "telegram_products")

CHANNELS = [
    "https://t.me/SHOPPOZONE",
    "https://t.me/DHARMimpex7780",
    "https://t.me/nika_enteprise",
    "https://t.me/shukansales",
    "https://t.me/sevenhorseonlinehub",
    "https://t.me/onlineproductbazar",
    "https://t.me/toyzone1"
]

client = OpenAI(api_key=OPENAI_KEY)

class DatabaseHandler:
    def __init__(self):
        self.connection: Optional[mysql.connector.MySQLConnection] = None
        self.ensure_database_exists()
        self.connect()
        self.create_table()

    def ensure_database_exists(self):
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            print(f"✅ Database '{DB_NAME}' is ready")
            cursor.close()
            conn.close()
        except Error as e:
            print(f"❌ Error creating database: {e}")

    def connect(self):
        try:
            if self.connection and self.connection.is_connected():
                return
            self.connection = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=True,
            )
            print("✅ Connected to MySQL database")
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            self.connection = None

    def create_table(self):
        create_table_query = """
       CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(500),
            product_description LONGTEXT,
            product_price FLOAT,
            channel_name VARCHAR(255),
            message_id BIGINT,
            timestamp DATETIME,
            media_url TEXT,
            source_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_message (channel_name, message_id)
        );

        """
        if not self.connection:
            return
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(create_table_query)
            print("✅ Products table is ready")
        except Error as e:
            print(f"❌ Error creating table: {e}")

    def insert_product(self, product: dict) -> bool:
        insert_query = """
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
        if not self.connection:
            return False

        # 🆕 Skip spammy product data before DB write
        if is_spammy_text(product.get("product_name", "")) or is_spammy_text(product.get("product_description", "")):
            print("🚫 Ignored spammy product message.")
            return False

        price_raw = str(product.get("product_price", "")).strip()
        price_match = re.search(r"(\d+(?:\.\d{1,2})?)", price_raw)
        product_price_float = float(price_match.group(1)) if price_match else 0.0

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    insert_query,
                    (
                        str(product.get("product_name", "")).strip(),
                        str(product.get("product_description", "")).strip(),
                        product_price_float,
                        str(product.get("channel_name", "")).strip(),
                        product.get("message_id", 0),
                        product.get("timestamp", datetime.utcnow()),
                        str(product.get("media_url", "")).strip(),
                        str(product.get("source_type", "telegram")).strip(),
                    ),
                )

            print(
                f"✅ Inserted/Updated: {product.get('product_name', '')} | "
                f"{product_price_float} | {product.get('channel_name', '')}"
            )
            return True
        except Error as e:
            print(f"❌ Error inserting product: {e}")
            return False

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("🔒 Database connection closed")


def is_spammy_text(text: str, product_price: str = "0") -> bool:
    text = text.strip()
    if not text:
        return True

    # Allow short text if a valid price exists
    if len(text) < 4 and product_price == "0":
        return True

    # Ratio of alphanumeric characters
    alnum_ratio = len(re.findall(r"[A-Za-z0-9]", text)) / max(len(text), 1)
    if alnum_ratio < 0.1 and product_price == "0":  # more lenient
        return True

    # Ratio of special characters
    special_ratio = len(re.findall(r"[^\w\s]", text)) / max(len(text), 1)
    if special_ratio > 0.7 and product_price == "0":
        return True

    # Only block if it contains obvious spam keywords AND no price
    spam_keywords = ["join", "order now", "buy now", "click", "telegram", "whatsapp", "offer"]
    if any(kw in text.lower() for kw in spam_keywords) and product_price == "0":
        return True

    return False


def clean_description(lines):

    meaningful_lines = []
    skip_patterns = [
        r"^\(?[A-Z]+\)?$",  # colors like (BROWN), RED
        r"Available✅+",
        r"In Stock",
        r"Out of Stock",
        r"❌.*?❌",  # stock out or other decorative markers
        r"^\s*[✅🔥💥]+\s*$",  # decorative symbols only
        r"^\(?[A-Za-z]{1,2}\)?$",  # very short words like (XL), (S)
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines matching decorative/irrelevant patterns
        if any(re.match(pat, line, re.IGNORECASE) for pat in skip_patterns):
            continue
        # Skip lines that are too short (less than 4 words)
        if len(line.split()) < 4:
            continue
        meaningful_lines.append(line)

    return "\n".join(meaningful_lines).strip()


def clean_message(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\d{6,12}", "", text)
    patterns_to_remove = [
        r"✅Avalaible",
        r"Avalaible",
        r"Available",
        r"✅ single price",
        r"🟢.*?PRICE.*?🟢",
        r"Join To Whatsapp Community.*",
        r"Join To Telegram Channel.*",
    ]
    for pat in patterns_to_remove:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n+", "\n", text).strip()
    return text


def extract_price(text: str) -> str:
    clean_text = text.replace(",", " ").replace("\n", " ")

    match = re.search(r"(?i)(?:₹|rs\.?|inr|price|rate)\s*[:\-]?\s*(\d+(?:\.\d{1,2})?)", clean_text)
    if match:
        return match.group(1)

    match = re.search(r"(?i)(\d+(?:\.\d{1,2})?)\s*(₹|rs\.?|inr|price|rate)", clean_text)
    if match:
        return match.group(1)

    clean_text = re.sub(r"\+?\b91\d{7,10}\b", "", clean_text)
    clean_text = re.sub(
        r"\b\d+\s*(cm|pcs|piece|pair|inch|inches|set|kg|g|ml|ltr|litre|size)\b",
        "",
        clean_text,
        flags=re.IGNORECASE,
    )

    candidates = re.findall(r"\b\d+(?:\.\d{1,2})?\b", clean_text)
    for num in reversed(candidates):
        val = float(num)
        if 1 < val < 9999:
            return num

    return "0"


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

    code_match = re.search(r"(SZ-\d{1,6}|SIZE\s*\d+)", text, re.IGNORECASE)
    product_code = code_match.group(1) if code_match else ""

    cleaned_text = text
    if product_price != "0":
        cleaned_text = re.sub(r"\b{}\b".format(re.escape(product_price)), "", cleaned_text)
    if product_code:
        cleaned_text = cleaned_text.replace(product_code, "")

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
        "Catalogue Link",
        "Order Now",
        "Shop Now",
        "Limited Stock",
        "DM us",
        "PM",
        "Offer",
        "discount",
        "link",
        "Buy Now",
        "🚨🚨❌❌STOCK OUT❌❌🚨🚨",
        "STOCK OUT ❌😂",
        "Available"
    ]

    for phrase in spam_phrases:
        cleaned_text = re.sub(re.escape(phrase), "", cleaned_text, flags=re.IGNORECASE)
    cleaned_text = cleaned_text.strip()

    # 🆕 Skip decorative/spammy messages automatically
    if is_spammy_text(cleaned_text):
        return {
            "product_name": "",
            "product_description": "",
            "product_price": "0",
            "channel_name": channel_name.lower(),
        }

    lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
    product_name = lines[0] if lines else ""
    product_description = ""
    if len(lines) > 1:
        product_description = clean_description(lines[1:])

    if product_code:
        if product_description:
            product_description += " " + product_code
        else:
            product_description = product_code
    prompt = f"""
    Extract product_name and product_description from the Telegram message.
    - Numbers at the start of product_name are allowed.
    - Do not include price or product code (e.g., SZ-xxxx) in product_name.
    - Ignore promotional phrases.
    - Return ONLY JSON with keys: product_name, product_description.
    Message: {cleaned_text}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = getattr(response.choices[0].message, "content", "").strip()
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            product_name = parsed.get("product_name", "").strip()
            product_description = parsed.get("product_description", "").strip()
    except Exception as e:
        print(f"❌ OpenAI error: {e}")

    if not product_name:
        lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
        if lines:
            product_name = lines[0][:500]
    if not product_description and product_code:
        product_description = product_code

    price_digits = re.search(r"\d+", str(product_price).replace(",", ""))
    final_price = price_digits.group() if price_digits else "0"

    return {
        "product_name": product_name,
        "product_description": product_description,
        "product_price": final_price,
        "channel_name": channel_name.lower(),
    }


async def scrape_channels():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    db = DatabaseHandler()
    tg_client = TelegramClient("scraper", API_ID, API_HASH)
    await tg_client.start()

    for channel in CHANNELS:
        async for message in tg_client.iter_messages(channel, limit=30):
            if not message.text:
                continue

            extracted = analyze_message(message.text, channel.split("/")[-1])

            product = {
                "product_name": extracted.get("product_name", ""),
                "product_description": extracted.get("product_description", ""),
                "product_price": extracted.get("product_price", ""),
                "channel_name": channel.split("/")[-1],
                "message_id": message.id,
                "timestamp": message.date,
                "media_url": "",
                "source_type": "telegram",
            }

            if message.media and isinstance(message.media, MessageMediaPhoto):
                file_path = await message.download_media(file="downloads/")
                product["media_url"] = file_path

            print(f"Channel: {product['channel_name']}")
            print(f"Product Name: {product['product_name']}")
            print(f"Description : {product['product_description']}")
            print(f"Price       : {product['product_price']}\n")

            db.insert_product(product)


if __name__ == "__main__":
    asyncio.run(scrape_channels())

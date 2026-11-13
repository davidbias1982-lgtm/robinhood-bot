import asyncio
import aiohttp
import time
from telegram import Bot
from telegram.constants import ParseMode

# ====================== SETTINGS ======================
TELEGRAM_TOKEN = "9186870767:AAHg_bdxFYOuvEBT7C48ZTzKm4lOhfXm6PE"
CHAT_ID = "7794688215"

# Higher number = fewer but higher quality alerts
MIN_SCORE = 72

# How often to scan (in seconds). 90 = every 1.5 minutes
SCAN_INTERVAL = 90

# ======================================================

bot = Bot(token=TELEGRAM_TOKEN)
seen_tokens = set()

async def get_robinhood_pairs(session):
    """Get recent pairs from DexScreener"""
    url = "https://api.dexscreener.com/latest/dex/pairs/robinhood"
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("pairs", [])[:40]
    except Exception as e:
        print("Error fetching pairs:", e)
    return []

async def safety_check(session, token_address):
    """Check safety with ScanHood"""
    url = f"https://scanhood.xyz/api/scan?token={token_address}"
    try:
        async with session.get(url, timeout=12) as resp:
            if resp.status == 200:
                return await resp.json()
    except:
        pass
    return None

def calculate_score(pair, safety):
    """Simple organic score (0-100)"""
    score = 50

    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    if liquidity > 25000:
        score += 15
    elif liquidity > 12000:
        score += 10
    elif liquidity > 6000:
        score += 5
    else:
        score -= 15

    volume = float(pair.get("volume", {}).get("h24", 0) or 0)
    if volume > 40000:
        score += 12
    elif volume > 15000:
        score += 8
    elif volume > 5000:
        score += 4

    txns = pair.get("txns", {}).get("h24", {})
    buys = int(txns.get("buys", 0) or 0)
    sells = int(txns.get("sells", 0) or 0)
    if buys + sells > 0:
        buy_ratio = buys / (buys + sells)
        if buy_ratio > 0.62:
            score += 10
        elif buy_ratio > 0.55:
            score += 5

    if safety:
        verdict = safety.get("verdict", "")
        if verdict == "PASS":
            score += 18
        elif verdict == "CAUTION":
            score += 5
        else:
            score -= 25

        if safety.get("sellable") is True:
            score += 8

    created = pair.get("pairCreatedAt")
    if created:
        age_hours = (time.time() * 1000 - created) / 1000 / 3600
        if 1 < age_hours < 18:
            score += 6

    return max(0, min(100, int(score)))

async def send_alert(pair, safety, score):
    base = pair.get("baseToken", {})
    name = base.get("name", "Unknown")
    symbol = base.get("symbol", "???")
    address = base.get("address", "")
    price = pair.get("priceUsd", "N/A")
    liquidity = pair.get("liquidity", {}).get("usd", 0)
    volume = pair.get("volume", {}).get("h24", 0)
    url = pair.get("url", "")

    verdict = safety.get("verdict", "Unknown") if safety else "Unknown"
    sellable = safety.get("sellable") if safety else None

    text = f"""
🚀 <b>S-Tier Alert</b> — Score: <b>{score}/100</b>

<b>{name}</b> (${symbol})
<code>{address}</code>

💰 Price: ${price}
💧 Liquidity: ${liquidity:,.0f}
📊 24h Volume: ${volume:,.0f}
🛡 Safety: {verdict}
✅ Sellable: {sellable}

<a href="{url}">DexScreener</a>
"""
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        print(f"Alert sent: {symbol} | Score {score}")
    except Exception as e:
        print("Failed to send alert:", e)

async def scan_loop():
    print("Scanner started...")
    async with aiohttp.ClientSession

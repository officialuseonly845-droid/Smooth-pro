"""
server.py - Main bot logic, Flask server, and scheduler for daily messages
"""

import os
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
import logging

# Import our API handler
from api import OpenRouterAPI, NewsAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize API handlers
openrouter = OpenRouterAPI()
news_api = NewsAPI()

# Bot configuration
BOT_NAME = "Smooth"
DAILY_MESSAGE_HOUR = 18  # 6 PM
DAILY_MESSAGE_MINUTE = 0
IST_TIMEZONE = pytz.timezone('Asia/Kolkata')


class SmoothBot:
    """Main bot logic handler"""
    
    @staticmethod
    def should_respond(message: str) -> bool:
        """
        Check if the bot should respond to this message
        Bot only responds if its name "Smooth" is mentioned
        
        Args:
            message: The incoming message text
            
        Returns:
            Boolean indicating if bot should respond
        """
        if not message:
            return False
        
        # Case-insensitive check for bot name
        return BOT_NAME.lower() in message.lower()
    
    @staticmethod
    def process_message(message: str) -> str:
        """
        Process incoming message and generate response
        
        Args:
            message: The user's message
            
        Returns:
            Bot's response string
        """
        # Check if bot should respond
        if not SmoothBot.should_respond(message):
            return ""  # Silent - don't respond
        
        # Get AI response from OpenRouter
        logger.info(f"Processing message: {message[:50]}...")
        result = openrouter.get_ai_response(message)
        
        # Return the reply (includes rate limit message if applicable)
        return result.get("reply", "I'm having trouble responding right now.")
    
    @staticmethod
    def generate_daily_message() -> str:
        """
        Generate the daily 6 PM message with quote and crypto news
        
        Returns:
            Formatted daily message string
        """
        logger.info("Generating daily message...")
        
        # Get motivational quote
        quote = news_api.get_motivational_quote()
        
        # Get crypto news
        crypto_news = news_api.get_crypto_news()
        
        # Combine into daily message
        daily_message = f"""
🌟 *Good Evening! Your Daily Update from Smooth* 🌟

{quote}

---

{crypto_news}

---

Have a wonderful evening! 🚀
"""
        return daily_message.strip()


# ============================================
# Flask Routes
# ============================================

@app.route('/', methods=['GET'])
def home():
    """
    Root endpoint for Uptime Robot to ping
    Keeps the bot alive 24/7
    """
    return jsonify({
        "status": "online",
        "bot": "Smooth",
        "message": "Bot is running smoothly! 🤖",
        "timestamp": datetime.now(IST_TIMEZONE).isoformat()
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Additional health check endpoint"""
    return jsonify({
        "status": "healthy",
        "bot": "Smooth",
        "timezone": "IST",
        "next_daily_message": f"{DAILY_MESSAGE_HOUR:02d}:{DAILY_MESSAGE_MINUTE:02d} IST"
    }), 200


@app.route('/message', methods=['POST'])
def handle_message():
    """
    Main message endpoint
    Accepts: { "message": "..." }
    Returns: { "reply": "..." }
    """
    try:
        # Parse JSON request
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                "error": "Invalid request",
                "message": "Please provide a 'message' field in JSON"
            }), 400
        
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({
                "error": "Empty message",
                "message": "Message cannot be empty"
            }), 400
        
        # Process the message
        bot_reply = SmoothBot.process_message(user_message)
        
        # If bot doesn't respond (name not mentioned), return empty reply
        if not bot_reply:
            return jsonify({
                "reply": "",
                "note": f"Bot only responds when '{BOT_NAME}' is mentioned in the message"
            }), 200
        
        # Return bot's reply
        return jsonify({
            "reply": bot_reply,
            "timestamp": datetime.now(IST_TIMEZONE).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/daily', methods=['GET'])
def get_daily_message():
    """
    Endpoint to manually trigger/view daily message
    Useful for testing
    """
    try:
        daily_msg = SmoothBot.generate_daily_message()
        return jsonify({
            "message": daily_msg,
            "timestamp": datetime.now(IST_TIMEZONE).isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error generating daily message: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500


# ============================================
# Scheduler for Daily Messages
# ============================================

def send_daily_message():
    """
    Function to send daily message at 6 PM IST
    In production, this would send to your messaging platform
    For now, it logs the message
    """
    try:
        daily_msg = SmoothBot.generate_daily_message()
        logger.info("=" * 60)
        logger.info("DAILY MESSAGE TRIGGERED AT 6 PM IST")
        logger.info("=" * 60)
        logger.info(daily_msg)
        logger.info("=" * 60)
        
        # TODO: Integrate with your messaging platform here
        # Examples:
        # - Send via Telegram: telegram_bot.send_message(chat_id, daily_msg)
        # - Send via WhatsApp: whatsapp_api.send_message(number, daily_msg)
        # - Send via Discord: discord_channel.send(daily_msg)
        # - Post to webhook: requests.post(webhook_url, json={"message": daily_msg})
        
    except Exception as e:
        logger.error(f"Error sending daily message: {str(e)}")


def init_scheduler():
    """
    Initialize the background scheduler for daily messages
    Schedules message to be sent at 6 PM IST every day
    """
    scheduler = BackgroundScheduler(timezone=IST_TIMEZONE)
    
    # Create cron trigger for 6 PM IST daily
    trigger = CronTrigger(
        hour=DAILY_MESSAGE_HOUR,
        minute=DAILY_MESSAGE_MINUTE,
        timezone=IST_TIMEZONE
    )
    
    # Add job to scheduler
    scheduler.add_job(
        func=send_daily_message,
        trigger=trigger,
        id='daily_message',
        name='Send daily message at 6 PM IST',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info(f"✅ Scheduler initialized! Daily messages will be sent at {DAILY_MESSAGE_HOUR:02d}:{DAILY_MESSAGE_MINUTE:02d} IST")
    
    return scheduler


# ============================================
# Application Entry Point
# ============================================

if __name__ == '__main__':
    # Initialize scheduler
    scheduler = init_scheduler()
    
    # Get port from environment variable (required for Render)
    port = int(os.getenv('PORT', 5000))
    
    # Log startup info
    logger.info("=" * 60)
    logger.info(f"🤖 Starting Smooth Bot")
    logger.info(f"📅 Current IST time: {datetime.now(IST_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"⏰ Daily messages scheduled for: {DAILY_MESSAGE_HOUR:02d}:{DAILY_MESSAGE_MINUTE:02d} IST")
    logger.info(f"🌐 Server starting on port: {port}")
    logger.info("=" * 60)
    
    try:
        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False  # Set to False in production
        )
    except (KeyboardInterrupt, SystemExit):
        # Graceful shutdown
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Bot stopped.")

import os
import requests
import schedule
import time
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread
import pytz
import re

app = Flask(__name__)

# Environment variables
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Store chat ID for daily news (can be extended to support multiple groups)
NEWS_CHAT_IDS = set()

def send_telegram_message(chat_id, text, pin=False):
    """Send message via Telegram Bot API"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        
        if pin and result.get('ok'):
            message_id = result['result']['message_id']
            pin_url = f"{TELEGRAM_API}/pinChatMessage"
            requests.post(pin_url, json={"chat_id": chat_id, "message_id": message_id})
        
        return result
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def send_telegram_photo(chat_id, photo_url, caption, pin=False):
    """Send photo via Telegram Bot API"""
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        
        if pin and result.get('ok'):
            message_id = result['result']['message_id']
            pin_url = f"{TELEGRAM_API}/pinChatMessage"
            requests.post(pin_url, json={"chat_id": chat_id, "message_id": message_id})
        
        return result
    except Exception as e:
        print(f"Error sending photo: {e}")
        return None

def get_openrouter_response(message):
    """Get AI response from OpenRouter API"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {
                "role": "system",
                "content": "You are Smooth, a friendly and helpful AI assistant. Keep responses concise and engaging."
            },
            {
                "role": "user",
                "content": message
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 429 or response.status_code == 402:
            return "I am bit tired 😪 can't reply right now"
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return "I am bit tired 😪 can't reply right now"
            
    except requests.exceptions.Timeout:
        return "I am bit tired 😪 can't reply right now"
    except Exception as e:
        print(f"OpenRouter error: {e}")
        return "I am bit tired 😪 can't reply right now"

def fetch_news_headlines():
    """Fetch news headlines from various sources"""
    news_data = {
        "crypto": [],
        "india": [],
        "world": []
    }
    
    try:
        # Using NewsAPI (you can replace with your preferred news API)
        # For demo purposes, we'll create a mock response
        # In production, use: https://newsapi.org or similar service
        
        news_data["crypto"] = [
            "Bitcoin surges past $45,000 amid institutional interest",
            "Ethereum 2.0 staking reaches new milestone",
            "Major crypto exchange announces new security features"
        ]
        
        news_data["india"] = [
            "Indian economy shows strong growth in Q3",
            "New tech hub announced in Bangalore",
            "Government launches digital initiative for farmers"
        ]
        
        news_data["world"] = [
            "Global climate summit reaches historic agreement",
            "Tech giants announce AI collaboration",
            "International space station welcomes new crew"
        ]
        
    except Exception as e:
        print(f"Error fetching news: {e}")
    
    return news_data

def format_news_post(news_data):
    """Format news into a beautiful post with emojis"""
    post = "📰 <b>Daily News Headlines</b> 📰\n"
    post += f"🕐 {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%B %d, %Y - %I:%M %p IST')}\n\n"
    
    # Crypto News
    post += "💰 <b>CRYPTO NEWS</b> 💰\n"
    for i, headline in enumerate(news_data["crypto"][:3], 1):
        post += f"  {i}. {headline}\n"
    post += "\n"
    
    # India News
    post += "🇮🇳 <b>INDIA NEWS</b> 🇮🇳\n"
    for i, headline in enumerate(news_data["india"][:3], 1):
        post += f"  {i}. {headline}\n"
    post += "\n"
    
    # World News
    post += "🌍 <b>WORLD NEWS</b> 🌍\n"
    for i, headline in enumerate(news_data["world"][:3], 1):
        post += f"  {i}. {headline}\n"
    post += "\n"
    
    post += "━━━━━━━━━━━━━━━━━━\n"
    post += "🤖 Powered by <b>Smooth Bot</b>"
    
    return post

def post_daily_news():
    """Post daily news to all registered chats"""
    print(f"Posting daily news at {datetime.now(pytz.timezone('Asia/Kolkata'))}")
    
    news_data = fetch_news_headlines()
    news_post = format_news_post(news_data)
    
    for chat_id in NEWS_CHAT_IDS:
        send_telegram_message(chat_id, news_post, pin=True)

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(60)

# Schedule daily news at 7 PM IST
ist = pytz.timezone('Asia/Kolkata')
schedule.every().day.at("19:00").do(post_daily_news)

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint for Uptime Robot"""
    return "Smooth bot is active", 200

@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint for bot interaction
    
    Expected JSON format:
    {
        "message": "Hey Smooth, how are you?",
        "chat_id": "123456789" (optional, for Telegram integration)
    }
    
    Returns:
    {
        "reply": "Bot response",
        "status": "success" or "ignored"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                "error": "Invalid request. 'message' field is required."
            }), 400
        
        user_message = data['message']
        chat_id = data.get('chat_id')
        
        # Register chat_id for daily news if provided
        if chat_id and chat_id not in NEWS_CHAT_IDS:
            NEWS_CHAT_IDS.add(chat_id)
        
        # Check if "Smooth" is mentioned in the message
        if not re.search(r'\bsmooth\b', user_message, re.IGNORECASE):
            return jsonify({
                "status": "ignored",
                "message": "Bot name not mentioned"
            }), 200
        
        # Get AI response
        bot_reply = get_openrouter_response(user_message)
        
        # Send via Telegram if chat_id provided
        if chat_id:
            send_telegram_message(chat_id, bot_reply)
        
        return jsonify({
            "status": "success",
            "reply": bot_reply
        }), 200
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Internal server error"
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            # Register chat for daily news
            if chat_id not in NEWS_CHAT_IDS:
                NEWS_CHAT_IDS.add(chat_id)
            
            # Check if "Smooth" is mentioned
            if re.search(r'\bsmooth\b', text, re.IGNORECASE):
                bot_reply = get_openrouter_response(text)
                send_telegram_message(chat_id, bot_reply)
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"ok": False}), 500

@app.route('/trigger-news', methods=['POST'])
def trigger_news():
    """Manual trigger for testing daily news (for development/testing only)"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({"error": "chat_id is required"}), 400
        
        NEWS_CHAT_IDS.add(chat_id)
        post_daily_news()
        
        return jsonify({
            "status": "success",
            "message": "News posted successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start scheduler in background thread
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

from flask import Flask
import threading
import asyncio
from telegram_master import main  # Assuming main() starts your Telegram bot
import os

app = Flask(__name__)

def run_telegram_bot():
    """Run the Telegram bot asynchronously in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())  # Start the Telegram bot

@app.route('/')
def home():
    """A simple route to test the Flask app."""
    return "Flask and Telegram bot are running!"

if __name__ == '__main__':
    # Run the Telegram bot in a separate thread
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()

    # Get the port from environment variables or default to 5000
    port = int(os.getenv('PORT', 5000))

    # Run Flask on the specified port
    app.run(host='0.0.0.0', port=port, use_reloader=False)  # use_reloader=False to avoid double running when in production
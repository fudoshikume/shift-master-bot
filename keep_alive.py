from flask import Flask
import threading
import asyncio
from telegram_master import main  # Assuming main() starts your Telegram bot

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

    # Run Flask in the main thread
    app.run(host='0.0.0.0', port=5000)
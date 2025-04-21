from flask import Flask
from threading import Thread
import asyncio
import telegram_master  # this must expose your `main()` function

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def start_flask():
    app.run(host='0.0.0.0', port=8000)

def start_bot():
    asyncio.run(telegram_master.main())

if __name__ == '__main__':
    # Start Flask in a separate thread
    Thread(target=start_flask).start()

    # Start the actual bot
    start_bot()
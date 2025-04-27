
from flask import Flask, Response
from threading import Thread
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    logger.info("Health check endpoint called")
    return Response("Bot is alive!", status=200)

@app.route('/ping')
def ping():
    logger.info("Ping endpoint called")
    return Response("pong", status=200)

def run():
    retries = 0
    max_retries = 5
    while retries < max_retries:
        try:
            logger.info("Starting keep-alive server on port 8080")
            app.run(host='0.0.0.0', port=8080, threaded=True)
            break
        except Exception as e:
            retries += 1
            logger.error(f"Keep-alive server error (attempt {retries}/{max_retries}): {e}")
            if retries >= max_retries:
                raise
            time.sleep(5)

def keep_alive():
    server_thread = Thread(target=run, daemon=True)
    try:
        server_thread.start()
        logger.info("Keep-alive thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start keep-alive thread: {e}")
        raise

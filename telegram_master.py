import requests
import datetime
import schedule
from telegram import Bot
from datetime import datetime, timedelta
from telegram.ext import CommandHandler, Application
import Shift_Master
from Shift_Master import check_and_notify, full_stats
from match_parser import check_and_parse_matches
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env file

TG_Token = os.getenv("TELEGRAM_TOKEN")


bot = Bot(token=TG_Token)

async def send_stats():
    print('gathering stats')
    text = await full_stats()
    await bot.sendMessage(chat_id='-4764440479', text=text)


async def send_loss_stats():
    text = await check_and_notify()
    if text:
        await bot.sendMessage(chat_id='-4764440479', text=text)

# f() to handle /stats
async def stats(update, context):
    await update.message.reply_text("*копається в гівні*...")
    result = await full_stats()
    await update.message.reply_text(result)

# f() to handle /losses
async def losses(update, context):
    await update.message.reply_text("*Перевіряє на запах ділдаки*...")
    result = await check_and_notify()
    if result:
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("За останню годину в соло ніхто не програвав")

# f() to make sure bot is running
async def start(update, context):
    await update.message.reply_text("Начальник зміни на проводі!")

async def help(update, context):
    await update.message.reply_text("Доступні команди: \n/help - список команд; \n/start - перевірка статусу Бота;\n/stats - отримати стату роботяг за останні 24 години;\n/losses - підтримати соло-невдах останньої години.")


async def main():
    scheduler = AsyncIOScheduler()

    # Wrapper only for check_and_notify
    async def send_loss_stats_wrapper():
        asyncio.create_task(send_loss_stats())  # ✅ Runs in background

    # Schedule tasks
    scheduler.add_job(check_and_parse_matches, "interval", minutes=10)  # ✅ No wrapper needed
    scheduler.add_job(send_stats, "cron", hour=2, minute=0)  # ✅ No wrapper needed
    scheduler.add_job(send_loss_stats_wrapper, "interval", minutes=60, misfire_grace_time=10)  # ✅ Wrapped

    scheduler.start()

    app = Application.builder().token(TG_Token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("losses", losses))
    app.add_handler(CommandHandler("help", help))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.sleep(float('inf'))  # Keeps everything running

asyncio.run(main())


"""async def scheduled_tasks():
    scheduler = AsyncIOScheduler()
    # Run check_and_parse_matches every minute
    scheduler.add_job(match_parser.check_and_parse_matches, 'interval', minutes=1)

    # Run full_stats every day at 2 AM
    scheduler.add_job(schedule_stats, 'cron', hour=2, minute=0)

    # Run check_and_notify every hour
    scheduler.add_job(schedule_loss_stats, 'interval', hours=1)

    await scheduler.start()

    while True:
        await asyncio.sleep(1)  # Keep the event loop running"""
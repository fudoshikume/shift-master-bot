import datetime
from telegram import Bot, Update
from telegram.ext import CommandHandler, Application, ContextTypes
from shift_master import check_and_notify, full_stats, add_player
from match_parser import check_and_parse_matches
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env file

TG_Token = os.getenv("TELEGRAM_TOKEN")
platform="telegram"

bot = Bot(token=TG_Token)

async def send_stats():
    print('gathering stats')
    text = await full_stats(platform)
    await bot.sendMessage(chat_id='-4764440479', text=text)


async def send_loss_stats():
    text = await check_and_notify()
    if text:
        await bot.sendMessage(chat_id='-4764440479', text=text)

# f() to handle /stats
async def stats(update, context):
    await update.message.reply_text("*копається в гівні*...")
    result = await full_stats(platform)
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

async def addplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Використання: /addplayer <steam_id> <telegram_nick> [discord_nick]")
        return

    steam_id = int(context.args[0])
    telegram_nick = context.args[1]
    discord_nick = context.args[2] if len(context.args) > 2 else None

    name_dict = {"telegram": telegram_nick}
    if discord_nick:
        name_dict["discord"] = discord_nick

    success = add_player(steam_id, name_dict)
    if success:
        await update.message.reply_text(f"✅ Гравця {telegram_nick} додано.")
    else:
        await update.message.reply_text(f"❌ Гравець із steam_id {steam_id} вже існує.")

async def main():
    app = Application.builder().token(TG_Token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("losses", losses))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("addplayer", addplayer))

    # Schedule recurring tasks
    app.job_queue.run_repeating(lambda context: asyncio.create_task(check_and_parse_matches()), interval=600)  # every 10 min
    app.job_queue.run_daily(lambda context: asyncio.create_task(send_stats()), time=datetime.time(hour=3, minute=0))  # at 3:00 AM
    app.job_queue.run_repeating(lambda context: asyncio.create_task(send_loss_stats()), interval=3600)  # every hour

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.sleep(float('inf'))  # Keeps everything running

asyncio.run(main())

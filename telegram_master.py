from datetime import time, datetime
from telegram import Bot, Update
from telegram.ext import CommandHandler, Application, ContextTypes, CallbackContext
import aiohttp
from match_parser import check_and_parse_matches
from match_stats import generate_weekly_report
from match_parser_instarun import run_loop
from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo
from match_collector_instarun import fetch_and_log_matches_for_last_day
from core import get_accusative_case, day_cases
import sys
import httpx
import asyncio

sys.path.append(os.path.dirname(__file__))
from shift_master import check_and_notify, full_stats, add_player, remove_player, Player

kyiv_zone = ZoneInfo("Europe/Kyiv")

load_dotenv()  # Load variables from .env file

TG_Token = os.getenv("TELEGRAM_TOKEN")
platform = "telegram"
chatID = os.getenv("CHAT_ID")
loop_task = None

bot = Bot(token=TG_Token)


async def heartbeat(context: CallbackContext):
    url = "https://shift-master-bot.onrender.com/"
    try:
        async with httpx.AsyncClient() as client:
            print("Heartbeat check...")
            response = await client.get(url)
            print(f"Heartbeat sent, status: {response.status_code}")
    except Exception as e:
        print(f"Heartbeat failed: {e}")


async def send_stats():
    print('gathering stats')
    await fetch_and_log_matches_for_last_day(1)
    text = await full_stats(platform)
    await bot.sendMessage(chat_id=chatID, text=text)


async def send_loss_stats():
    await fetch_and_log_matches_for_last_day(1)
    text = await check_and_notify(platform)
    if text:
        await bot.sendMessage(chat_id=chatID, text=text)


async def send_weekly_stats():
    await fetch_and_log_matches_for_last_day(7)
    message = generate_weekly_report("telegram")
    await bot.send_message(chat_id=chatID, text=message)


async def weekly(update, context):
    await update.message.reply_text("👀*проглядає архіви*...")
    await fetch_and_log_matches_for_last_day(7)
    message = generate_weekly_report(platform)
    await update.message.reply_text(message)


# f() to handle /stats
async def stats(update, context):
    await update.message.reply_text("*копається в гівні*...")
    await fetch_and_log_matches_for_last_day(1)
    result = await full_stats(platform)
    await update.message.reply_text(result)


# f() to handle /losses
async def losses(update, context):
    await update.message.reply_text("*Перевіряє на запах ділдаки*...")
    await fetch_and_log_matches_for_last_day(1)
    result = await check_and_notify(platform)
    if result:
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("За останню годину в соло ніхто не програвав")


# f() to make sure bot is running
async def start(update, context):
    print("Received /start command")  # Log to see if this is triggered
    await update.message.reply_text("Начальник зміни на проводі!")


async def gethelp(update, context):
    await update.message.reply_text(
        "Доступні команди: \n/gethelp - список команд; \n/start - перевірка статусу Бота;\n/stats - отримати стату роботяг за останні 24 години;\n/losses - підтримати соло-невдах останньої години.\n/addplayer <steam_id> <telegram_nick> <discord_nick - опційно> - Додати досьє гравця до теки. * Steam ID і telegram nickname обов'язкові\n/removeplayer <Steam_ID32> Видалити досьє гравця з теки.\n/weekly - загальна статистика банди за тиждень(NEW)\nБільше інфи в @chuck.singer")


async def addplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Використання: /addplayer <steam_id32> <telegram_nick> [discord_nick]")
        return

    steam_id = context.args[0]
    if not steam_id.isdigit():
        await update.message.reply_text("❌ Steam ID має бути числом.")
        return

    steam_id = int(steam_id)
    telegram_nick = context.args[1]
    discord_nick = context.args[2] if len(context.args) > 2 else None

    # Validate steam_id via OpenDota
    nickname = Player.validate_steam_id(steam_id)
    if not nickname:
        await update.message.reply_text("❌ Не вдалося знайти гравця за цим Steam ID.")
        return

    name_dict = {"telegram": telegram_nick}
    if discord_nick:
        name_dict["discord"] = discord_nick

    # Temporarily store pending data for confirmation
    context.user_data["pending_add"] = {
        "steam_id": steam_id,
        "name_dict": name_dict,
        "od_nick": nickname,
    }

    await update.message.reply_text(
        f"🔍 Знайдено гравця з ніком: *{nickname}*.\n"
        f"Додати до списку? Напиши /yes або /no протягом 5 хвилин.",
        parse_mode="Markdown"
    )

    # Schedule timeout job
    context.job_queue.run_once(
        timeout_pending_add,
        when=300,
        data={
            "chat_id": update.effective_chat.id,
            "user_id": update.effective_user.id
        },
        name=f"pending_add_{update.effective_user.id}"
    )


async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_data = context.application.user_data.get(user_id, {}).get("pending_add")

    if not pending_data:
        await update.message.reply_text("⚠️ Немає гравця для підтвердження.")
        return

    steam_id = pending_data["steam_id"]
    name_dict = pending_data["name_dict"]

    success = add_player(steam_id, name_dict)
    if success:
        await update.message.reply_text(f"✅ Гравця {name_dict.get('telegram')} додано.")
    else:
        await update.message.reply_text(f"❌ Гравець із steam_id {steam_id} вже існує.")

    # Clear the pending add and cancel timeout
    context.application.user_data[user_id].pop("pending_add", None)
    job = context.application.user_data[user_id].pop("pending_add_job", None)
    if job:
        job.schedule_removal()


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending = context.application.user_data.get(user_id, {}).get("pending_add")

    if not pending:
        await update.message.reply_text("⚠️ Немає гравця для скасування.")
        return

    context.application.user_data[user_id].pop("pending_add", None)
    job = context.application.user_data[user_id].pop("pending_add_job", None)
    if job:
        job.schedule_removal()

    await update.message.reply_text("❌ Додавання скасовано.")


async def timeout_pending_add(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    # Remove pending add request if it still exists
    if "pending_add" in context.application.user_data[user_id]:
        del context.application.user_data[user_id]["pending_add"]
        await context.bot.send_message(
            chat_id=chat_id,
            text="⌛️ Час на підтвердження вийшов. Гравця не додано."
        )


async def removeplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to remove a player by their Steam ID"""
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Використання: /removeplayer <steam_id>.\nНе забудь додати Steam_ID")
        return

    steam_id = context.args[0]  # Extract Steam ID from command arguments
    response = remove_player(steam_id, platform="telegram")
    await update.message.reply_text(response)


async def fetch_and_log_matches(update: Update, context: CallbackContext):
    days_before = int(context.args[0]) if context.args else 1  # Default to 1 day if no argument is passed
    await update.message.reply_text(f"Гортаю звіти за {days_before} {get_accusative_case(days_before, day_cases)}")
    await fetch_and_log_matches_for_last_day(days=days_before)
    await update.message.reply_text(
        f"Перевірив звіти за зміни з {days_before} {get_accusative_case(days_before, day_cases)}.")


async def start_parser(update, context):
    """Start the parser loop."""
    global loop_task
    try:
        days = int(context.args[0]) if context.args else 7  # Default to 7 days
        if loop_task and not loop_task.done():
            await update.message.reply_text("Парсер вже працює!")
            return

        # Define the callback function to send a message when parsing is done
        async def send_completion_message(message):
            await update.message.reply_text(message)

        # Start the loop with the 'days' parameter and the callback
        loop_task = asyncio.create_task(run_loop(days, send_message_callback=send_completion_message))
        await update.message.reply_text(
            f"Парсер запущено, робимо матчі за остатні {days} {get_accusative_case(days, day_cases)}.")
    except Exception as e:
        await update.message.reply_text(f"Шось пішло не так: {e}")


async def stop_parser(update, context):
    """Stop the parser loop."""
    global loop_task
    if loop_task and not loop_task.done():
        loop_task.cancel()
        await update.message.reply_text("Парсер зупинено.")
    else:
        await update.message.reply_text("Нема шо зупиняти.")


# Setup the Telegram bot handlers
def setup_handlers(app):
    app.add_handler(CommandHandler("parse", start_parser))  # Start command
    app.add_handler(CommandHandler("stopparse", stop_parser))  # Stop command


async def main():
    app = Application.builder().token(TG_Token).build()

    setup_handlers(app)
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("losses", losses))
    app.add_handler(CommandHandler("gethelp", gethelp))
    app.add_handler(CommandHandler("addplayer", addplayer))
    app.add_handler(CommandHandler("removeplayer", removeplayer))
    app.add_handler(CommandHandler("yes", confirm_add))
    app.add_handler(CommandHandler("no", cancel_add))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("collect", fetch_and_log_matches))

    # Schedule recurring tasks
    app.job_queue.run_repeating(lambda context: asyncio.create_task(check_and_parse_matches()),
                                interval=600)  # every 10 min
    app.job_queue.run_repeating(heartbeat, interval=60, first=0)
    app.job_queue.run_daily(
        lambda context: asyncio.create_task(send_stats()),
        time=time(hour=3, minute=0, tzinfo=kyiv_zone)
    )
    app.job_queue.run_repeating(lambda context: asyncio.create_task(fetch_and_log_matches_for_last_day(1)),
                                interval=21600)  # every 6 hrs
    app.job_queue.run_repeating(lambda context: asyncio.create_task(send_loss_stats()), interval=600)  # every 10 min
    app.job_queue.run_daily(
        callback=send_weekly_stats,
        time=time(hour=15, minute=0),  # 15:00 UTC
        days=(0,),  # Sunday (0 = Monday, so 6 = Saturday)
        name="weekly_report"
    )

    max_retries = 5
    retry_delay = 5

    try:
        # Initialize the app and start polling
        print(f"Initializing bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for attempt in range(max_retries):
            try:
                await app.initialize()
                await app.run_polling()  # Use run_polling() instead of start_polling()
                await bot.send_message(chat_id=chatID, text="на проводі")
                print("Bot successfully started and polling")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Connection attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(retry_delay)
                else:
                    raise
        else:
            print("Failed to start the bot after retries.")
            return

        # Ensure the bot is still running and verify its connection
        while True:  # Inner loop to maintain the bot running
            try:
                await asyncio.sleep(60)  # Check every minute
                print(f"Bot heartbeat check - still running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await bot.get_me()  # Verify connection to Telegram
            except asyncio.CancelledError:
                print("Bot task was cancelled")
                break
            except Exception as e:
                print(f"Error in main loop at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error details: {str(e)}")
                print(f"Connection will be retried...")
                import traceback
                print(f"Traceback:\n{traceback.format_exc()}")
                continue

    except Exception as e:
        print(f"Critical error at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")


asyncio.run(main())

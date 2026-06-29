from datetime import time
from telegram import Update
from telegram.ext import CommandHandler, Application, ContextTypes, CallbackContext
import db
from shift_master import check_and_notify, full_stats, Player, generate_invoke_msg
from match_stats import generate_weekly_report, generate_all_time_report
from match_parser_instarun import run_loop
import asyncio
from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo
from match_collector_instarun_db import fetch_and_log_matches_for_last_day
from core import get_accusative_case, day_cases
from aiohttp import web
import aiohttp
from db import remove_player, add_player
from telegram.error import Conflict

kyiv_zone = ZoneInfo("Europe/Kyiv")
load_dotenv()
TG_Token = os.getenv("TELEGRAM_TOKEN")
platform="telegram"
loop_task = None

async def safe_start_polling(application):
    try:
        await application.updater.start_polling()
        print("[BOT] Polling started successfully.")
    except Conflict:
        print("[BOT] Another instance is running. Stopping this one.")
        await application.stop()

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

async def check_bot_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
    # Перевіримо чи бот має права на повідомлення (можна додати інші права)
    can_post_messages = getattr(chat_member, 'can_post_messages', True)  # True для супергруп і каналів за замовчуванням
    can_read_messages = chat_member.status in ['administrator', 'member']
    return can_post_messages and can_read_messages

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    title = update.effective_chat.title

    # Перевіряємо, чи канал вже в базі
    if db.channel_exists(chat_id):
        await update.message.reply_text("Я і так вже тут начальник!")
        return

    # Перевіряємо права бота у каналі
    has_perms = await check_bot_permissions(update, context)
    if not has_perms:
        await update.message.reply_text("Дай мені доступ до особових справ! (потрібні права адміністратора)")
        return

    # Додаємо канал у базу

    try:
        await db.add_channel(chat_id, title)
        await update.message.reply_text("У вас тепер новий нач по кадрах!")
    except Exception as e:
        await update.message.reply_text(f"Щось пішло не так при додаванні каналу: {e}")

async def send_stats(app, channels):
    print('gathering stats')
    for channel in channels:
        await fetch_and_log_matches_for_last_day(channel, days=1)
        text = await full_stats(platform, channel)
        await app.bot.sendMessage(chat_id=channel, text=text)

async def send_loss_stats(app, channels):
    for channel in channels:
        await fetch_and_log_matches_for_last_day(channel, days=1)
        text = await check_and_notify(channel, platform)
        if text:
            await app.bot.sendMessage(chat_id=channel, text=text)

async def send_weekly_stats(app, channels):
    for channel in channels:
        await fetch_and_log_matches_for_last_day(channel, 7)
        message = await generate_weekly_report(channel, platform)
        await app.bot.send_message(chat_id=channel, text=message)

async def alltime(update, context):
    await update.message.reply_text("👀*розчищає підвал*...")
    channel = update.message.chat_id
    await fetch_and_log_matches_for_last_day(channel, days=1)
    message = await generate_all_time_report(channel, platform)
    await update.message.reply_text(message)

async def weekly(update, context):
    await update.message.reply_text("👀*проглядає архіви*...")
    channel = update.message.chat_id
    await fetch_and_log_matches_for_last_day(channel, days=1)
    message = await generate_weekly_report(channel, platform)
    await update.message.reply_text(message)

async def stats(update, context):
    await update.message.reply_text("*копається в гівні*...")
    channel = update.message.chat_id
    await fetch_and_log_matches_for_last_day(channel, days=1)
    result = await full_stats(platform, channel)
    await update.message.reply_text(result)

async def losses(update, context):
    await update.message.reply_text("*Перевіряє на запах ділдаки*...")
    channel = update.message.chat_id
    await fetch_and_log_matches_for_last_day(channel, days=1)
    result = await check_and_notify(channel, platform)
    if result:
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("За останню годину в соло ніхто не програвав")

# f() to make sure bot is running
async def status(update, context):
    await update.message.reply_text("Начальник зміни на проводі!")

async def gethelp(update, context):
    help_lines = [
        "🤖 *Доступні команди:*",
        "/gethelp — список команд;",
        "/status — перевірка статусу Бота;",
        "/stats — стата роботяг за останні 24 години;",
        "/losses — підтримати соло-невдах останньої години;",
        "/addplayer <steam_id> <telegram_nick> <discord_nick (опційно)> — додати досьє гравця до теки.",
        "   * Steam ID і telegram nickname — обов'язкові;",
        "/removeplayer <steam_id32> — видалити досьє гравця з теки;",
        "/weekly — загальна статистика банди за тиждень (🆕);",
        "/alltime — загальна статистика заводу за весь час (🆕)"
        "/collect X — зібрати інфу про матчі за останні X днів (стандартно — 7);",
        "/parse X — пропарсити матчі за X днів (стандартно — 7) [Застаріла];",
        "/stopparse — зупинити парсер [Застаріла];",
        "/invoke — закликати всіх на завод 🏭",
        "",
        "📎 Більше інфи — [@chuck.singer](https://t.me/chuck.singer)"
    ]
    await update.message.reply_text("\n".join(help_lines), parse_mode="Markdown")

async def invoke(update, context):
    channel_id = update.message.chat_id
    message = await generate_invoke_msg(platform, channel_id)  # platform is global
    await update.message.reply_text(message)

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

    nickname = Player.validate_steam_id(steam_id)
    if not nickname:
        await update.message.reply_text("❌ Не вдалося знайти гравця за цим Steam ID.")
        return

    name_dict = {"telegram": telegram_nick}
    if discord_nick:
        name_dict["discord"] = discord_nick

    context.user_data["pending_add"] = {
        "steam_id": steam_id,
        "name": name_dict,
        "od_nick": nickname,
        "channel_ids": [update.effective_chat.id]  # Додаємо chat_id відразу сюди
    }

    await update.message.reply_text(
        f"🔍 Знайдено гравця з ніком: *{nickname}*.\n"
        f"Додати до списку? Напиши /yes або /no протягом 5 хвилин.",
        parse_mode="Markdown"
    )

    job = context.job_queue.run_once(
        timeout_pending_add,
        when=300,
        data={
            "chat_id": update.effective_chat.id,
            "user_id": update.effective_user.id
        },
        name=f"pending_add_{update.effective_user.id}"
    )

    context.user_data["pending_add_job"] = job

async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_data = context.user_data.get("pending_add")
    user_id = update.effective_user.id

    if not pending_data:
        await update.message.reply_text("⚠️ Немає гравця для підтвердження.")
        return

    # Якщо хочеш додатково гарантувати, що поточний чат в channel_ids
    chat_id = update.effective_chat.id
    if chat_id not in pending_data.get("channel_ids", []):
        pending_data["channel_ids"].append(chat_id)

    success = add_player(pending_data)

    msg = "✅ Гравця додано." if success else "ℹ️ Гравець вже існує або сталася помилка."
    await update.message.reply_text(msg)

    job = context.user_data.pop("pending_add_job", None)
    if job:
        job.schedule_removal()

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending = context.user_data.get(user_id, {}).get("pending_add")

    if not pending:
        await update.message.reply_text("⚠️ Немає гравця для скасування.")
        return

    context.user_data[user_id].pop("pending_add", None)
    job = context.user_data[user_id].pop("pending_add_job", None)
    if job:
        job.schedule_removal()

    await update.message.reply_text("❌ Додавання скасовано.")

async def timeout_pending_add(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    # Remove pending add request if it still exists
    if "pending_add" in context*.user_data[user_id]:
        del context.user_data[user_id]["pending_add"]
        await context.bot.send_message(
            chat_id=chat_id,
            text="⌛️ Час на підтвердження вийшов. Гравця не додано."
        )

async def removeplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Використання: /removeplayer <steam_id>\nНе забудь додати Steam ID.")
        return

    steam_id = context.args[0]
    try:
        steam_id = int(steam_id)
    except ValueError:
        await update.message.reply_text("⚠️ Неправильний формат Steam ID. Має бути число.")
        return

    # Отримуємо id поточного чату
    channel_id = str(update.effective_chat.id)

    response = remove_player(steam_id=steam_id, channel_id=channel_id)
    await update.message.reply_text(response)

async def fetch_and_log_matches(update: Update, context: CallbackContext):
    days_before = int(context.args[0]) if context.args else 1  # Default to 1 day if no argument is passed
    channel_id = str(update.effective_chat.id)
    await update.message.reply_text(f"Гортаю звіти за {days_before} {get_accusative_case(days_before, day_cases)}")
    await fetch_and_log_matches_for_last_day(days=days_before, channel_id=channel_id)
    await update.message.reply_text(f"Перевірив звіти за зміни з {days_before} {get_accusative_case(days_before, day_cases)}.")

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
        await update.message.reply_text(f"Парсер запущено, робимо матчі за остатні {days} {get_accusative_case(days, day_cases)}.")
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
    async with aiohttp.ClientSession() as session:
        await session.post(f"https://api.telegram.org/bot{TG_Token}/deleteWebhook")

    await start_web_server()

    application = Application.builder().token(TG_Token).build()
    # Setup the HTTP server

    channels = db.get_channels()

    setup_handlers(application)
    # Setup handlers (e.g., your command handlers)
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("losses", losses))
    application.add_handler(CommandHandler("gethelp", gethelp))
    application.add_handler(CommandHandler("addplayer", addplayer))
    application.add_handler(CommandHandler("removeplayer", removeplayer))
    application.add_handler(CommandHandler("yes", confirm_add))
    application.add_handler(CommandHandler("no", cancel_add))
    application.add_handler(CommandHandler("weekly", weekly))
    application.add_handler(CommandHandler("collect", fetch_and_log_matches))
    application.add_handler(CommandHandler("invoke", invoke))
    application.add_handler(CommandHandler("alltime", alltime))

    # Schedule recurring tasks using job_queue (no polling here)
    application.job_queue.run_daily(
        lambda context: asyncio.create_task(send_stats(application, channels)),
        time=time(hour=3, minute=0, tzinfo=kyiv_zone)
    )
    # application.job_queue.run_repeating(lambda context: asyncio.create_task(fetch_and_log_matches_for_last_day(1)), interval=79201)
    application.job_queue.run_repeating(lambda context: asyncio.create_task(send_loss_stats(application, channels)), interval=3590)
    application.job_queue.run_daily(
        lambda context: asyncio.create_task(send_weekly_stats(application, channels)),
        time=time(hour=15, minute=0),
        days=(0,),  # Sunday (0)
        name="weekly_report"
    )

    # Initialize the application and start the bot
    await application.initialize()
    await application.start()
    await application.bot.delete_webhook(drop_pending_updates=True)  # optional safety
    await safe_start_polling(application)

    # ✅ Keep alive without causing loop conflicts
    await asyncio.Event().wait()

# Check if the loop is already running
if __name__ == "__main__":
    asyncio.run(main())
import discord
from discord.ext import commands
from shift_master import Player
import datetime
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

players = []

intents = discord.Intents.default()
intents.messages = True  # Дозволяє читати повідомлення
intents.guilds = True  # Дозволяє працювати з серверами
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def get_solo_losses():
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    solo_loss_players = []

    for player in players:
        matches = player.get_recent_matches()
        for match in matches:
            match_time = datetime.utcfromtimestamp(match["start_time"]+match["duration"])
            if match_time < one_hour_ago:
                break  # Matches are sorted, no need to check older ones

            if match["player_slot"] < 128:  # Radiant side
                is_loss = not match["radiant_win"]
            else:  # Dire side
                is_loss = match["radiant_win"]

            if is_loss and match.get("party_size") == 1:
                solo_loss_players.append(player.name)
                break
    return solo_loss_players


@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущений і готовий до роботи!")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def stats(ctx):
    stats = [
            "Стата за остатні 24 години:",
            "---------------------------"
        ]
    player: Player
    for player in players:
        stats.append(player.fetch_and_count_games())
        message = "\n".join(stats)
    print(message)

    await ctx.send(message)

@bot.command()
async def loss(ctx):
    solo_loss_players = get_solo_losses()
    if solo_loss_players:
        for player in solo_loss_players:
            await ctx.send_message(f"{player}, НТ, старенький, як вже є :(")
    else:
        await ctx.send("За остатню годину ніхто в соло не зливав! <3")

bot.run(TOKEN)
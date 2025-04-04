from typing import Any
import requests
import datetime
import aiohttp
import asyncio

from django.db.models.query_utils import select_related_descend
#import schedule
from telegram import Bot
from datetime import datetime, timedelta

bot = Bot(token='7605785848:AAHomujEg_sQuk9B1rODOnb9TjHGoOrcFjk')


def get_match_end_time(match) -> datetime.timestamp:
    match_start_game = datetime.fromtimestamp(match['start_time'])
    match_duration = timedelta(seconds=match['duration'])
    match_end_time = match_start_game + match_duration
    return match_end_time

def player_win(match) -> True | False:
    player_radiant = (match['player_slot'] <= 127)
    if player_radiant == match['radiant_win']:
        return True
    else:
        return False

### below goes class Player with attr and methods for handling:
class Player:
    abc = 123
    def __init__(self, steam_id, name):
        self.steam_id = steam_id
        self.name = name
        self.total_games = 0
        self.solo_games = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_duration = 0

    async def get_recent_matches(self):
        """returns json view of player's recent matches"""
        url = f'https://api.opendota.com/api/players/{self.steam_id}/Matches'
        limit = {"date": 1}
        response = requests.get(url, params=limit)

        if response.status_code != 200:
            print("Error fetching data from OpenDota API.")
            return None
        matches = response.json()
        return matches

    async def fetch_and_count_games(self) -> str | None:
        """returns text stats representation (games, solo, wins, losses within last 24H) for 1 Player obj"""
        matches = await self.get_recent_matches()
        if matches is None:
            return None
        time_marker = datetime.now() - timedelta(days=1)

        for match in matches:
            match_end_time = get_match_end_time(match)
            self.total_duration += match['duration']
            #print(f"match: {match['match_id']}\nparty size: {match['party_size']}\nend time:{match_end_time}")
            if match_end_time >= time_marker:
                self.total_games += 1
                #parsematch(match["match_id"])
                if match["party_size"] == 1:
                    self.solo_games += 1
                if player_win(match):
                    self.total_wins += 1

        self.total_losses = self.total_games - self.total_wins

        if not self.total_games:
            player_stats = f'У {self.name} сьогодні відгул\n'
        else:
            player_stats = f'Братішка {self.name} зіграв загалом {self.total_games} каток! ({self.total_wins} розджЕбав, {self.total_losses} закинув), \nНа це вбив {timedelta(seconds=self.total_duration)} свого життя.\nВсоляново награв {self.solo_games}! WP, GN ^_^!\n'
        return player_stats

async def get_solo_losses() -> list:
    """f() that returns list of player.name in Players, who have lost solo games within last 60 min"""
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    solo_loss_players = []

    for player in players:
        matches = await player.get_recent_matches()
        for match in matches:
            #print(f"match: {match['match_id']}\nparty size: {match['party_size']}\nend time:{get_match_end_time(match)}")
            match_end_time = get_match_end_time(match)
            if match_end_time < one_hour_ago:
                break  # Matches are sorted, no need to check older ones
                #datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(t, datetime.UTC).

            if (not player_win(match)) and (match.get("party_size") == 1 | 0):
                solo_loss_players.append(player.name)
                break
    return solo_loss_players

async def check_and_notify() -> str:
    """f() sends message to Telegram group based on result from get_solo_losses()"""
    message = [""]
    compiled_msg = ""
    solo_loss_players = await get_solo_losses()
    if solo_loss_players:
        for player in solo_loss_players:
            message.append(f"{player}, НТ, старенький, як вже є :(")
        compiled_msg = "\n".join(message)
    else:
        compiled_msg = ""
    await asyncio.sleep(0.1)
    return compiled_msg


async def full_stats() -> str:
    '''this f() gets all players' 24H stats (by running fetch_and_count_games()) and sends it all in a TG group message'''
    compiled_stats = [
            "Стата за остатні 24 години:",
            "---------------------------"
        ]
    player: Player | Any
    message = ""
    for player in players:
        compiled_stats.append(await player.fetch_and_count_games())
        message = "\n".join(compiled_stats)
        player.total_games = 0
        player.total_wins = 0
        player.total_losses = 0
        player.solo_games = 0
        player.total_duration = 0
    return message

# this is a list of Player objs - Gachi Club residents
players = [
    Player(60939193, '@basturmate'),
    Player(91979951, '@chuck_singer'),
    Player(113464386, '@matwey_k'),
    Player(378156730, '@Honey_Badger'),
    Player(180785888, '@boikevich-Turbo'),
    Player(196765629, '@Женя'),
    Player(154210795, '@SKantor1'),
    Player(1513957386, '@bobokaja'),
    Player(195364625, '@jwl_s'),
    Player(153518750, '@m_ANJ'),
    Player(221564662, '@dimon4egkl')]

## BELOW is commands handling
async def main():
    print(await full_stats())
    print(await check_and_notify())


if __name__ == "__main__":
    asyncio.run(main())
"""
# f() to handle /stats
async def stats(update, context):
    await update.message.reply_text("*копається в гівні*...")
    await update.message.reply_text(full_stats())

# f() to handle /losses
async def losses(update, context):
    await update.message.reply_text("*Перевіряє на запах ділдаки*...")
    await update.message.reply_text(full_stats())

# f() to make sure bot is running
async def start(update, context):
    await update.message.reply_text("Начальник зміни на проводі!")

async def help(update, context):
    await update.message.reply_text("Доступні команди: \n/help - список команд; \n/start - перевірка статусу Бота;\n/stats - отримати стату роботяг за останні 24 години;\n/losses - підтримати соло-невдах останньої години.")

def main():
    app = Application.builder().token("7605785848:AAHomujEg_sQuk9B1rODOnb9TjHGoOrcFjk").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("losses", losses))
    app.add_handler(CommandHandler("help", help))

    schedule.every().day.at("00:00").do(full_stats)
    schedule.every(1).hours.do(check_and_notify)

    app.run_polling()

main()"""


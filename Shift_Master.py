from typing import Any
import requests
import datetime
import asyncio
from datetime import datetime, timedelta

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
            match_end_time = get_match_end_time(match)
            if match_end_time < one_hour_ago:
                break  # Matches are sorted, no need to check older ones

            if (not player_win(match)) and (match.get("party_size") == 1 | 0):
                solo_loss_players.append(player.name)
                break
    return solo_loss_players

async def check_and_notify() -> str:
    """f() sends message to Telegram group based on result from get_solo_losses()"""
    message = [""]
    solo_loss_players = await get_solo_losses()
    for player in solo_loss_players:
        message.append(f"{player}, НТ, старенький, вже як є :(")
    compiled_msg = "\n".join(message)
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


#todo: - clear_stats,
# add_player,
# enclose players in .csv



from typing import Any
import requests
import datetime
import asyncio
import csv
import json
from datetime import datetime, timedelta, timezone



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

    @staticmethod
    def get_match_end_time(match) -> datetime.timestamp:
        match_start_game = datetime.fromtimestamp(match['start_time'], tz=timezone.utc)
        match_duration = timedelta(seconds=match['duration'])
        match_end_time = match_start_game + match_duration
        return match_end_time

    @staticmethod
    def player_win(match) -> True | False:
        player_radiant = (match['player_slot'] <= 127)
        if player_radiant == match['radiant_win']:
            return True
        else:
            return False

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

    async def fetch_and_count_games(self, platform) -> str | None:
        """returns text stats representation (games, solo, wins, losses within last 24H) for 1 Player obj"""
        matches = await self.get_recent_matches()
        if matches is None:
            return None
        time_marker = datetime.now(timezone.utc) - timedelta(days=1)

        for match in matches:
            match_end_time = Player.get_match_end_time(match)
            self.total_duration += match['duration']
            #print(f"match: {match['match_id']}\nparty size: {match['party_size']}\nend time:{match_end_time}")
            if match_end_time >= time_marker:
                self.total_games += 1
                if match["party_size"] == 1:
                    self.solo_games += 1
                if Player.player_win(match):
                    self.total_wins += 1

        self.total_losses = self.total_games - self.total_wins

        if not self.total_games:
            player_stats = f'У {self.name.get(platform)} сьогодні відгул\n'
        else:
            player_stats = f'Братішка {self.name.get(platform)} зіграв загалом {self.total_games} каток! ({self.total_wins} розджЕбав, {self.total_losses} закинув), \nНа це вбив {timedelta(seconds=self.total_duration)} свого життя.\nВсоляново награв {self.solo_games}! WP, GN ^_^!\n'
        return player_stats

    def clear_stats(self):
        self.total_games = 0
        self.solo_games = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_duration = 0

async def get_solo_losses(platform) -> list:
    """f() that returns list of player.name in Players, who have lost solo games within last 60 min"""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    solo_loss_players = []
    players = load_players_from_csv()
    for player in players:
        matches = await player.get_recent_matches()
        for match in matches:
            match_end_time = Player.get_match_end_time(match)
            if match_end_time < one_hour_ago:
                break  # Matches are sorted, no need to check older ones

            if (not Player.player_win(match)) and (match.get("party_size") < 2):
                solo_loss_players.append(player.name.get(platform))
                break
    return solo_loss_players

async def check_and_notify(platform) -> str:
    """f() sends message to Telegram group based on result from get_solo_losses()"""
    message = [""]
    solo_loss_players = await get_solo_losses(platform)
    for player in solo_loss_players:
        message.append(f"{player}, НТ, старенький, вже як є :(")
    compiled_msg = "\n".join(message)
    await asyncio.sleep(0.1)
    return compiled_msg

def load_players_from_csv(filename="players.csv"):
    players = []
    with open(filename, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            steam_id = row["steam_id"]
            name = json.loads(row["name"])  # convert back from string to dict
            player = Player(steam_id, name)
            players.append(player)
    return players

def add_player(steam_id, name_dict):
    players = load_players_from_csv()
    if any(p.steam_id == steam_id for p in players):
        return False  # Player already exists

    new_player = Player(steam_id, name_dict)
    players.append(new_player)
    save_players_to_csv(players)
    return True

def remove_player(steam_id, platform=None):
    """Remove a player from the CSV file based on steam_id"""
    players = load_players_from_csv()  # Load current players from CSV
    player_to_remove = None

    for player in players:
        if player.steam_id == steam_id:
            player_to_remove = player
            break

    if player_to_remove:
        players.remove(player_to_remove)
        save_players_to_csv(players)  # Save the updated list back to CSV
        if platform:
            return f"Гравця {player_to_remove.name.get(platform)} з Steam ID {steam_id} видалено з теки."
        return f"Гравця {steam_id} видалено з теки."
    else:
        return f"Гравця з Steam ID {steam_id} не знайдено в теці."

def save_players_to_csv(players, filename="players.csv"):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["steam_id", "name"])
        for player in players:
            writer.writerow([player.steam_id, json.dumps(player.name)])

async def full_stats(platform) -> str:
    '''this f() gets all players' 24H stats (by running fetch_and_count_games()) and sends it all in a TG group message'''
    compiled_stats = [
            "Стата за остатні 24 години:",
            "---------------------------"
        ]
    player: Player | Any
    message = ""
    players = load_players_from_csv()
    for player in players:
        compiled_stats.append(await player.fetch_and_count_games(platform))
        message = "\n".join(compiled_stats)
        player.clear_stats()
    return message

#todo:




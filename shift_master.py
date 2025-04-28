import requests
import datetime
import asyncio
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from core import names, get_accusative_case

### below goes class Player with attr and methods for handling:
class Player:
    def __init__(self, steam_id, name):
        self.steam_id = steam_id
        self.name = name
        self.daily_games = 0
        self.daily_solo = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.total_duration = 0

    @staticmethod
    def validate_steam_id(steam_id: int) -> str | None:
        """Validate a Steam ID using OpenDota API and return nickname if valid."""
        try:
            response = requests.get(f"https://api.opendota.com/api/players/{steam_id}")
            if response.status_code != 200:
                return None

            data = response.json()
            profile = data.get("profile")
            if not profile:
                return None

            return profile.get("personaname")
        except Exception:
            return None

    def update_daily_stats(self, matches: list):
        """Updates this player's daily stats based on recent matches."""
        now = datetime.now(timezone.utc)
        recent_matches = [
            m for m in matches

            if self.steam_id in m.player_ids and m.endtime and now - m.endtime <= timedelta(days=1)
        ]

        self.daily_games = len(recent_matches)
        self.daily_wins = sum(1 for m in recent_matches if m.win_status)
        self.daily_losses = sum(1 for m in recent_matches if not m.win_status)
        self.daily_solo = sum(1 for m in recent_matches if m.solo_status)
        self.total_duration = sum(m.duration for m in recent_matches if m.duration is not None)

    async def fetch_and_count_games(self, platform) -> str | None:
        if not self.daily_games:
            player_stats = f'У {self.name.get(platform)} сьогодні відгул\n'
        else:
            game_cases = ('катку', 'катки', 'каток')
            solo_text = f"Всоляново награв {self.daily_solo} {get_accusative_case(self.daily_solo, game_cases)}."
            if not self.daily_solo:
                solo_text = "Всоляново не грав"
            player_stats = f'{random.choice(names)} {self.name.get(platform)} зіграв загалом {self.daily_games} {get_accusative_case(self.daily_games, game_cases)}! ({self.daily_wins} розджЕбав, {self.daily_losses} закинув), \nНа це вбив {timedelta(seconds=self.total_duration)} свого життя.\n{solo_text} WP, GN ^_^!\n'
        return player_stats

    def clear_stats(self):
        self.daily_games = 0
        self.daily_solo = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.total_duration = 0

async def get_last_hour_solo_losers(matches: list, players: list, platform) -> list:
    """f() that returns list of player.name in Players, who have lost solo games within last 60 min"""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    solo_losers = []
    for player in players:
        for match in matches:
            if (
                    player.steam_id in match.player_ids and
                    match.solo_status and
                    match.win_status is False and
                    match.endtime and match.endtime >= one_hour_ago
            ):
                solo_losers.append(player.name.get(platform, player.name.get("telegram")))
                break  # Don't double count this player, one solo loss is enough

    return solo_losers

async def check_and_notify(platform) -> str:
    """f() returns message to messenger bot based on result from get_solo_losses()"""
    from match_stats import Match
    message = [""]
    matches = Match.read_matches_from_csv("matchlog.csv")
    players = load_players_from_csv("players.csv")
    solo_loss_players = await get_last_hour_solo_losers(matches, players, platform)
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
            steam_id = int(row["steam_id"])  # ← force int here
            name = json.loads(row["name"])
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

async def collect_daily_stats(matches, players):
    for player in players:
        player.update_daily_stats(matches)

async def generate_daily_report(platform, players):
    compiled_stats = [
        "Стата за остатні 24 години:",
        "---------------------------"
    ]
    for player in players:
        compiled_stats.append(await player.fetch_and_count_games(platform))
        player.clear_stats()
    return "\n".join(compiled_stats)

async def generate_invoke_msg(platform):
    players = load_players_from_csv()
    nickname_list = []
    for p in players:
        nickname_list.append(p.name[platform])
    message = "\n".join(nickname_list) + "\nГайда на завод!"
    return message

async def full_stats(platform) -> str:
    from match_stats import Match
    players = load_players_from_csv()
    matches = Match.read_matches_from_csv("matchlog.csv")
    await collect_daily_stats(matches, players)
    return await generate_daily_report(platform, players)

#todo:




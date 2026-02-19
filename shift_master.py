import asyncio
import random
from datetime import datetime, timedelta, timezone

import aiohttp
import requests

from core import get_accusative_case, names, rank_id_to_tier


class Player:
    def __init__(self, steam_id, name):
        self.steam_id = steam_id
        self.name = name
        self.daily_games = 0
        self.daily_solo = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.total_duration = 0
        self.current_rank = 0
        self.channel_ids = []

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
        print(f"DEBUG {self.steam_id}: now={now.isoformat()}")
        for m in matches:
            if self.steam_id in m.player_ids:
                delta = now - m.endtime if isinstance(m.endtime, datetime) else "BAD_TYPE"
                if delta <= timedelta(days=7):
                    print(f"[MATCH] {m.match_id} | ended {m.endtime} | delta={delta}")

        recent_matches = [
            m
            for m in matches
            if self.steam_id in m.player_ids and m.endtime and now - m.endtime <= timedelta(days=1)
        ]
        print(f"DEBUG {self.steam_id}: counted {len(recent_matches)} recent matches")

        self.daily_games = len(recent_matches)
        self.daily_wins = sum(1 for m in recent_matches if m.win_status)
        self.daily_losses = sum(1 for m in recent_matches if not m.win_status)
        self.daily_solo = sum(1 for m in recent_matches if m.solo_status)
        self.total_duration = sum(m.duration for m in recent_matches if m.duration is not None)

    async def fetch_and_count_games(self, platform) -> str | None:
        if not self.daily_games:
            player_stats = f"У {self.name.get(platform)} ({rank_id_to_tier.get(self.current_rank)}) сьогодні відгул\n"
        else:
            game_cases = ("катку", "катки", "каток")
            solo_text = f"Всоляново награв {self.daily_solo} {get_accusative_case(self.daily_solo, game_cases)}."
            if not self.daily_solo:
                solo_text = "Всоляново не грав"
            player_stats = f"{random.choice(names)} {self.name.get(platform)} ({rank_id_to_tier.get(self.current_rank)}) зіграв загалом {self.daily_games} {get_accusative_case(self.daily_games, game_cases)}! ({self.daily_wins} розджЕбав, {self.daily_losses} закинув), \nНа це вбив {timedelta(seconds=self.total_duration)} свого життя.\n{solo_text} WP, GN ^_^!\n"
        return player_stats

    async def get_current_rank(self):
        url = f"https://api.opendota.com/api/players/{self.steam_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rank_tier = data.get("rank_tier", 0)
                        return rank_tier if rank_tier is not None else 0
                    else:
                        print(f"❗ Failed to fetch rank for {self.steam_id}, status {resp.status}")
                        return 0
        except Exception as e:
            print(f"❗ Exception while fetching rank for {self.steam_id}: {e}")
            return 0

    def clear_stats(self):
        self.daily_games = 0
        self.daily_solo = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.total_duration = 0


async def update_rank(platform, channel):
    msg = [""]
    import db

    players = await db.get_channel_players(channel)

    for player in players:
        old_rank = player.current_rank
        new_rank = await player.get_current_rank()

        if old_rank != new_rank:
            db.update_player(player.steam_id, {"current_rank": new_rank})

            if old_rank == 0:
                msg.append(
                    f"🫡 Для {player.name.get(platform)} заведено поточний ранг "
                    f"{rank_id_to_tier.get(new_rank)}!\n"
                )
            elif old_rank < new_rank:
                msg.append(
                    f"👑 {random.choice(names)} {player.name.get(platform)} апнув ранг "
                    f"з {rank_id_to_tier.get(old_rank)} до {rank_id_to_tier.get(new_rank)}! "
                    "Найщиріші конгратуляції!\n🍻🍻🍻\n"
                )
            else:
                msg.append(
                    f"🩼 {random.choice(names)} {player.name.get(platform)} спустився "
                    f"з {rank_id_to_tier.get(old_rank)} до {rank_id_to_tier.get(new_rank)}! "
                    "НТ, скоро так в дізабіліті дріфт підеш!\n🦞🦞🦞\n"
                )

    print("\n".join(msg))
    return msg


async def get_last_hour_solo_losers(matches: list, players: list, platform) -> list:
    """f() that returns list of player.name in Players, who have lost solo games within last 60 min"""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(minutes=70)
    solo_losers = []
    for player in players:
        for match in matches:
            if (
                player.steam_id in match.player_ids
                and match.solo_status
                and match.win_status is False
                and match.endtime
                and match.endtime >= one_hour_ago
            ):
                solo_losers.append(player.name.get(platform, player.name.get("telegram")))
                break  # Don't double count this player, one solo loss is enough

    return solo_losers


async def check_and_notify(channel, platform) -> str:
    """f() returns message to messenger bot based on result from get_solo_losses()"""
    import db

    message = [""]
    matches = await db.get_logged_match_objects()
    players = await db.get_channel_players(channel)
    solo_loss_players = await get_last_hour_solo_losers(matches, players, platform)
    for player in solo_loss_players:
        message.append(f"{player}, НТ, старенький, вже як є :(")
    compiled_msg = "\n".join(message)
    await asyncio.sleep(0.1)
    return compiled_msg


async def collect_daily_stats(matches, players):
    print("DEBUG DAILY STATS")
    print(f"matches: {len(matches)}\nplayers: {len(players)}")
    for player in players:
        print(f"Debug player {player.steam_id}: {player.name.get('telegram')}")
        player.update_daily_stats(matches)


async def generate_daily_report(platform, players):
    compiled_stats = ["Стата за остатні 24 години:", "---------------------------"]
    for player in players:
        name = player.name.get(platform)
        if not name:
            print(f"DEBUG: {name} Player {player.steam_id} has no name for platform '{platform}'")
        res = await player.fetch_and_count_games(platform)
        if res is None:
            res = f"{player.name.get(platform, 'Unknown')} статистика відсутня"
        compiled_stats.append(res)
        player.clear_stats()
    return "\n".join(compiled_stats)


async def generate_invoke_msg(platform, channel_id):
    import db

    players = await db.get_channel_players(channel_id)
    nickname_list = []
    for p in players:
        nickname_list.append(f"{random.choice(names)} {p.name[platform]}")
    message = "\n".join(nickname_list) + "\nГайда на завод!"
    return message


async def full_stats(platform, channel) -> str:
    import db

    rank_msg = await update_rank(platform, channel)
    players = await db.get_channel_players(channel)
    matches = await db.get_logged_match_objects()
    await collect_daily_stats(matches, players)
    msg = await generate_daily_report(platform, players)
    if len(rank_msg) > 1:
        msg += "\n⚔️⚔️⚔️ Зміни рангів ⚔️⚔️⚔️\n"
        msg += "\n".join(rank_msg)
    else:
        msg += "\n\n🗿🗿 Змін в рангах немає... 🗿🗿"
    return msg

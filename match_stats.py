import aiohttp
import requests
import datetime
import csv
import os
import json
import asyncio

from flask.cli import load_dotenv

from core import player_win, get_match_end_time, names, GAME_MODES
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List
from collections import Counter
import random
import httpx


load_dotenv()

GRAPHQL_URL = "https://api.stratz.com/graphql"
OD_API_URL = "https://api.opendota.com/api/matches/"
STRATZ_TOKEN = os.getenv("STRATZ_API_TOKEN")
QUERY_TEMPLATE = """
query {
  match(id: MATCH_ID_PLACEHOLDER) {
    players {
      steamAccountId
      partyId
    }
  }
}"""

@dataclass
@dataclass
class Match:
    match_id: int
    player_ids: List[int]
    win_status: bool
    endtime: datetime
    duration: int
    solo_status: bool | None = None
    match_mode: int = 0  # ✅ default to Unknown (see core.py -> GAME_MODE_NAMES)

    @staticmethod
    async def get_recent_matches(steam_id: int, days: int = 1, limit: int = 10, offset: int = 0, after_match_id: int | None = None) -> list:
        """Fetch recent matches for a given player (steam_id) in the last N days."""
        url = f"https://api.opendota.com/api/players/{steam_id}/matches"

        params = {"date": days,
                  "limit": limit,
                  "offset": offset,
                  "after_match_id": after_match_id}
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"Failed to fetch matches for {steam_id}")
            return []

        return response.json()

    @staticmethod
    async def create_new_matches_from_recent(steam_id: int, known_ids: list) -> list:
        raw_matches = await Match.get_recent_matches(steam_id)
        new_matches = []

        for raw in raw_matches:
            match_id = raw["match_id"]

            if match_id in known_ids:
                continue

            participants = []
            for pid in known_ids:
                if pid == raw.get("account_id"):
                    participants.append(pid)

            match = Match(
                match_id=match_id,
                player_ids=participants if participants else [steam_id],
                win_status=player_win(raw),
                solo_status=await is_player_solo_in_match(match_id, steam_id),
                endtime=get_match_end_time(raw),
                duration=raw.get("duration", 0),
                match_mode=raw.get("game_mode", 0),
            )

            new_matches.append(match)

        return new_matches

    @staticmethod
    def write_matches_to_csv(matches: list, filename='matchlog.csv', overwrite=False):
        file_exists = os.path.exists(filename)

        mode = 'w' if overwrite else 'a'

        with open(filename, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not file_exists or overwrite:
                writer.writerow(
                    ["match_id", "player_ids", "win_status", "solo_status", "endtime", "duration", "match_mode"]
                )

            for match in matches:
                writer.writerow([
                    match.match_id,
                    ';'.join(str(pid) for pid in match.player_ids),
                    int(match.win_status),
                    "1" if match.solo_status is True else "0" if match.solo_status is False else "",
                    match.endtime.isoformat() if match.endtime else "",
                    match.duration,
                    match.match_mode,
                ])

def read_matches_from_csv(filename='matchlog.csv') -> list:
    matches = []

    if not os.path.exists(filename):
        return matches

    try:
        with open(filename, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                if not row["match_id"] or row["match_id"] == "match_id":
                    continue

                # Parse solo_status safely
                solo_raw = row.get("solo_status", "").strip()
                if solo_raw == "1":
                    solo_status = True
                elif solo_raw == "0":
                    solo_status = False
                else:
                    solo_status = None

                # Parse match_mode safely (as int if possible, else 0)
                match_mode_raw = row.get("match_mode", "").strip()
                try:
                    match_mode = int(match_mode_raw) if match_mode_raw else 0
                except ValueError:
                    match_mode = 0

                match = Match(
                    match_id=int(row["match_id"]),
                    player_ids=[int(pid) for pid in row["player_ids"].split(";") if pid],
                    win_status=json.loads(row["win_status"]),
                    solo_status=solo_status,
                    endtime=datetime.fromisoformat(row["endtime"]) if row["endtime"] else None,
                    duration=int(row["duration"]) if row["duration"] else 0,
                    match_mode=match_mode  # correctly assigned here
                )
                matches.append(match)
    except Exception as e:
        print(f"[ERROR] Reading matches from CSV failed: {e}")

    return matches

def get_last_week_matches():
    matches = read_matches_from_csv()
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return [m for m in matches if m.endtime > one_week_ago]

async def fetch_and_log_matches():
    from shift_master import load_players_from_csv
    players = load_players_from_csv()
    player_ids = [player.steam_id for player in players]

    for player in players:
        new_matches = await Match.create_new_matches_from_recent(player.steam_id, player_ids)
        Match.write_matches_to_csv(new_matches)

def get_player_counters(matches: list) -> tuple[Counter, Counter, Counter, Counter]:
    games_played = Counter()
    wins = Counter()
    losses = Counter()
    solo = Counter()
    match_durations = {}  # match_id -> (duration, [player_ids], endtime)

    for m in matches:
        for pid in m.player_ids:
            games_played[pid] += 1
            if m.win_status:
                wins[pid] += 1
            else:
                losses[pid] += 1
            if m.solo_status:
                solo[pid] += 1
        match_durations[m.match_id] = (m.endtime, m.player_ids)

    return games_played, wins, losses, solo

def get_longest_match(matches: list, players: list) -> str:
    if not matches:
        return "Немає зіграних ігор для аналізу тривалості."

    # Find the match with the maximum duration
    longest = max(matches, key=lambda m: m.duration)

    # Convert duration to minutes and seconds
    minutes, seconds = divmod(longest.duration, 60)
    duration_str = f"{minutes} хв {seconds} с"

    # Convert endtime to readable date
    date_str = longest.endtime.strftime('%Y-%m-%d %H:%M')

    # Find player names
    def get_name(pid):
        for p in players:
            if p.steam_id == pid:
                return p.name.get("telegram", str(pid))
        return str(pid)

    player_names = ", ".join([get_name(pid) for pid in longest.player_ids])

    return (
        f"\n🕰️ *Найдовша гра:* {duration_str}\n"
        f"📅 {date_str}\n"
        f"👥 Гравці: {player_names}"
    )

def generate_weekly_summary(matches: list, players: list, platform: str) -> str:
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_matches = [m for m in matches if m.endtime > one_week_ago]

    if not recent_matches:
        return "📉 За останній тиждень ігор не знайдено."

    total = len(recent_matches)
    wins = sum(m.win_status for m in recent_matches)
    winrate = round((wins / total) * 100, 1)

    games_played, wins_by_player, losses_by_player, solo_games = get_player_counters(recent_matches)

    def get_name(pid):
        for p in players:
            if p.steam_id == pid:
                return p.name.get(platform) or f"👤{pid}"
        return f"👤{pid}"

    # Track player stats with winrate and lossrate
    player_stats = {}
    for player_id in games_played:
        games_count = games_played[player_id]
        wins_count = wins_by_player.get(player_id, 0)
        losses_count = losses_by_player.get(player_id, 0)
        solo_count = solo_games.get(player_id, 0)

        winrate_player = round((wins_count / games_count) * 100, 1) if games_count > 0 else 0
        lossrate_player = round((losses_count / games_count) * 100, 1) if games_count > 0 else 0

        player_stats[get_name(player_id)] = {
            'games_played': games_count,
            'wins': wins_count,
            'winrate': winrate_player,
            'solo_games': solo_count,
            'lossrate': lossrate_player,
        }

    # Best winrate and worst lossrate players
    best_winrate_player = max(player_stats.items(), key=lambda x: x[1]['winrate'])
    worst_lossrate_player = max(player_stats.items(), key=lambda x: x[1]['lossrate'])

    top_played_id, top_played_count = games_played.most_common(1)[0]
    top_win_id, top_win_count = wins_by_player.most_common(1)[0]
    top_loss_id, top_loss_count = losses_by_player.most_common(1)[0]
    top_solo_id, top_solo_count = solo_games.most_common(1)[0]

    top_played = get_name(top_played_id)
    top_win = get_name(top_win_id)
    top_loss = get_name(top_loss_id)
    top_solo = get_name(top_solo_id)

    # Longest match info
    longest_match_str = get_longest_match(recent_matches, players)

    # Prepare the player stats list
    player_stats_list = '\n'.join(
        [f"{random.choice(names)} {name} - Ігор: {stats['games_played']}, Перемог: {stats['wins']} ({stats['winrate']}%) | Поразок: {stats['games_played'] - stats['wins']} ({stats['lossrate']}%) | "
         f"Соло: {stats['solo_games']}"
         for name, stats in player_stats.items()]
    )

    return (
        f"🗓️ *Тижневий звіт:*\n"
        f"🎮 Ігор зіграно: *{total}*\n"
        f"🏆 Виграно: *{wins}* ({winrate}%)\n"
        f"👑 Найбільше ігор: {random.choice(names)} {top_played} ({top_played_count})\n"
        f"🥇 Найбільше перемог: {random.choice(names)} {top_win} ({top_win_count})\n"
        f"💀 Найбільше поразок: {random.choice(names)} {top_loss} ({top_loss_count})\n"
        f"🧍‍♂️ Найбільше соло-ігор: {random.choice(names)} {top_solo} ({top_solo_count})\n"
        f"🏅 Найкращий Winrate: {best_winrate_player[0]} ({best_winrate_player[1]['winrate']}%)\n"
        f"💔 Найгірший Lossrate: {worst_lossrate_player[0]} ({worst_lossrate_player[1]['lossrate']}%)\n"
        f"📊 Статистика гравців:\n{player_stats_list}\n"
        f"{longest_match_str}"
    )

def generate_weekly_report(platform: str) -> str:
    from shift_master import load_players_from_csv
    players = load_players_from_csv()
    matches = read_matches_from_csv()
    return generate_weekly_summary(matches, players, platform)

def generate_all_time_report(platform: str) -> str:
    from shift_master import load_players_from_csv
    matches = read_matches_from_csv("matchlog.csv")
    players = load_players_from_csv()
    player_map = {p.steam_id: p for p in players}

    # 1. Total matches and game mode breakdown
    total_matches = len(matches)
    mode_counts = {}
    for match in matches:
        mode = match.match_mode or "Unknown"
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    # 2. Player stats
    from collections import defaultdict
    games_played = defaultdict(int)
    wins = defaultdict(int)
    solo_games = defaultdict(int)

    for match in matches:
        for pid in match.player_ids:
            games_played[pid] += 1
            if match.solo_status:
                solo_games[pid] += 1
            if match.win_status:
                wins[pid] += 1

    stats = []
    for pid, count in sorted(games_played.items(), key=lambda x: x[1], reverse=True):
        player = player_map.get(pid)
        name = player.name.get(platform, str(pid)) if player else str(pid)
        winrate = wins[pid] / count * 100 if count else 0
        solos = solo_games.get(pid, 0)
        stats.append(f"{name}: {count} ігор, {winrate:.1f}% WR, {solos} соло")

    # 3. Longest match
    longest_match = max(matches, key=lambda m: m.duration, default=None)

    # Final report
    msg = "📊 УСІ ЧАСИ 📊\n"
    msg += f"🔢 Всього матчів: {total_matches}\n"

    msg += "\n📚 Режими гри:\n"
    for mode, count in mode_counts.items():
        msg += f"• {GAME_MODES.get(mode)}: {count}\n"

    msg += "\n🏅 Статистика гравців:\n"
    msg += "\n".join(stats)

    if longest_match:
        mins = longest_match.duration // 60
        secs = longest_match.duration % 60
        duration_str = f"{mins} хв {secs:02} с"

        mode_str = GAME_MODES.get(longest_match.match_mode, f"Невідомий режим ({longest_match.match_mode})")

        outcome_str = "🔵 Виграна нашими" if longest_match.win_status else "🔴 Поразка наших"

        tracked_players = []
        for pid in longest_match.player_ids:
            player = player_map.get(pid)
            if player:
                nickname = player.name.get(platform, str(pid))
                tracked_players.append(nickname)

        msg += "\n\n🐌 Найдовша гра:\n"
        msg += f""
        msg += f"⏱ Тривалість: {duration_str}\n"
        msg += f"🎮 Режим: {mode_str}\n"
        msg += f"{outcome_str}\n"
        msg += f"👥 Наші гравці: {', '.join(tracked_players)}\n"
        msg += f"🆔 Match ID: {longest_match.match_id}"

    return msg

async def fetch_match_from_stratz(match_id: int) -> dict | None:
    query = QUERY_TEMPLATE.replace("MATCH_ID_PLACEHOLDER", str(match_id))

    headers = {
        "Authorization": f"Bearer {STRATZ_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "STRATZ_API"
    }

    payload = {"query": query}
    # print(json.dumps(payload, indent=2))
    # print(json.dumps(headers, indent=4))
    async with httpx.AsyncClient() as client:
        response = await client.post(GRAPHQL_URL, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json().get("data", {}).get("match")
        return data
    else:
        print(f"[STRATZ] Error {response.status_code}: {response.text}")
        return None

async def is_player_solo_in_match(match_id, steam_id: int) -> bool | None:
    """
    Returns True if the player was solo (no partyId),
    False if in a party,
    None if player not found or data is malformed.
    """
    match_data = await fetch_match_from_stratz(match_id)
    if not match_data or "players" not in match_data:
        print(f"[⚠️] Could not retrieve players for match {match_id}")
        return None

    for player in match_data["players"]:
        if player.get("steamAccountId") == steam_id:
            return player.get("partyId") is None

    return None  # Player not found in match

"""here comes temp stuff to test out how stratz API works. I try and get solo status from stratz for the unparsed matches we logged"""

# async def fetch_match_mode(match_id: int) -> int:
#     async with httpx.AsyncClient() as client:
#         try:
#             resp = await client.get(f"{OD_API_URL}{match_id}")
#             if resp.status_code == 200:
#                 data = resp.json()
#                 return data.get("game_mode", 0) or 0
#             else:
#                 print(f"[OD] Failed to fetch {match_id}: {resp.status_code}")
#         except Exception as e:
#             print(f"[OD] Exception fetching {match_id}: {e}")
#     return 0
#
# async def update_match_modes(matches: list):
#     count =0
#     for i, match in enumerate(matches):
#         if not match.match_mode or match.match_mode == 0:
#             old_mode = match.match_mode
#             match.match_mode = await fetch_match_mode(match.match_id)
#             print(f"Updated match {match.match_id}. {GAME_MODES.get(old_mode)} -> {GAME_MODES.get(match.match_mode)} ---\|/--- ({i+1}/{len(matches)})")
#             count+=1
#             await asyncio.sleep(0.5)  # To avoid rate limit
#
#     # Rewrite the file after all updates
#     Match.write_matches_to_csv(matches, overwrite=True)
#     print(f"✅ matchlog.csv rewritten with {count} updated match_modes")
#
async def main():
    matches = read_matches_from_csv()
    print(generate_all_time_report("telegram"))

if __name__ == '__main__':
    asyncio.run(main())

# async def update_all_solo_status_stratz():
#     matches = read_matches_from_csv()
#     updated = False
#     count = 0
#
#     for match in matches:
#         # Assumes first player is the tracked one
#         steam_id = match.player_ids[0]
#         new_status = await is_player_solo_in_match(match.match_id, steam_id)
#         print(f"{match.match_id} -> \nold solo staus - {match.solo_status}, \nnew status - {new_status}")
#
#         if new_status is not None and new_status != match.solo_status:
#             print(f"🔄 Match {match.match_id} solo status changed to {new_status}")
#             match.solo_status = new_status
#             updated = True
#             count += 1
#
#
#         # Sleep to avoid STRATZ rate limits (5 req/sec = 0.2s delay)
#         await asyncio.sleep(1.1)
#
#     if updated:
#         Match.write_matches_to_csv(matches)
#         print(f"💾 Matchlog updated with {count} new solo statuses.")
#     else:
#         print("✅ No changes needed.")

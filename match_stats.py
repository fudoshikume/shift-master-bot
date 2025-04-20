import requests
import datetime
import csv
import os
import json
from core import player_win, get_match_end_time, names
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter
import random


@dataclass
class Match:
    match_id: int
    player_ids: List[int] = field(default_factory=list)
    win_status: Optional[bool] = None
    solo_status: Optional[bool] = None
    endtime: Optional[datetime] = None
    duration: int = 0

    @staticmethod
    async def get_recent_matches(steam_id: int, days: int = 1) -> list:
        """Fetch recent matches for a given player (steam_id) in the last N days."""
        url = f"https://api.opendota.com/api/players/{steam_id}/matches"
        params = {"date": days}
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

            # Skip if already known
            if match_id in known_ids:
                continue

            # Look for other known players who were in this match
            participants = []
            for pid in known_ids:
                if pid == raw.get("account_id"):  # This might vary based on the API
                    participants.append(pid)

            match = Match(
                match_id=match_id,
                player_ids=participants if participants else [steam_id],
                win_status=player_win(raw),
                solo_status=raw.get("party_size") == 1,
                endtime=get_match_end_time(raw),
                duration=raw.get("duration", 0)
            )

            new_matches.append(match)

        return new_matches

    @staticmethod
    def write_matches_to_csv(matches: list, filename='matchlog.csv'):
        file_exists = os.path.exists(filename)

        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header if file is new
            if not file_exists:
                writer.writerow(["match_id", "player_ids", "win_status", "solo_status", "endtime", "duration"])

            for match in matches:
                writer.writerow([
                    match.match_id,
                    ';'.join(str(pid) for pid in match.player_ids),
                    int(match.win_status),
                    int(match.solo_status),
                    match.endtime.isoformat() if match.endtime else "",
                    match.duration
                ])

    @staticmethod
    def read_matches_from_csv(filename='matchlog.csv') -> list:
        matches = []

        if not os.path.exists(filename):
            return matches  # No file yet = no matches

        try:
            with open(filename, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)  # ← Use DictReader to read headers

                for row in reader:
                    if not row["match_id"] or row["match_id"] == "match_id":
                        continue  # skip empty or malformed rows

                    match = Match(
                        match_id=int(row["match_id"]),
                        player_ids=[int(pid) for pid in row["player_ids"].split(";") if pid],
                        win_status=json.loads(row["win_status"]),
                        solo_status=json.loads(row["solo_status"]),
                        endtime=datetime.fromisoformat(row["endtime"]) if row["endtime"] else None,
                        duration=int(row["duration"]) if row["duration"] else 0
                    )
                    matches.append(match)

        except Exception as e:
            print(f"[Error] Reading matchlog: {e}")

        return matches

def get_last_week_matches():
    matches = Match.read_matches_from_csv()
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

    return (
        f"🗓️ *Тижневий звіт:*\n"
        f"🎮 Ігор зіграно: *{total}*\n"
        f"🏆 Виграно: *{wins}* ({winrate}%)\n"
        f"👑 Найбільше ігор: {random.choice(names)} {top_played} ({top_played_count})\n"
        f"🥇 Найбільше перемог: {random.choice(names)} {top_win} ({top_win_count})\n"
        f"💀 Найбільше поразок: {random.choice(names)} {top_loss} ({top_loss_count})\n"
        f"🧍‍♂️ Найбільше соло-ігор: {random.choice(names)} {top_solo} ({top_solo_count})"
        f"{longest_match_str}"
    )

def generate_weekly_report(platform: str) -> str:
    from shift_master import load_players_from_csv
    players = load_players_from_csv()
    matches = Match.read_matches_from_csv()
    return generate_weekly_summary(matches, players, platform)
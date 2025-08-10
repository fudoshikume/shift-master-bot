import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
from db import get_channel_players, add_matches, update_match, get_logged_matches
from match_stats import Match, is_player_solo_in_match
from core import player_win, get_match_end_time

def parse_player_ids(raw_player_ids):
    if isinstance(raw_player_ids, str):
        # Стара форма, рядок із роздільниками
        return [int(pid) for pid in raw_player_ids.split(";") if pid.strip()]
    elif isinstance(raw_player_ids, list):
        return raw_player_ids
    else:
        return []

def parse_datetime(dt):
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        # Припустимо, що рядок у форматі ISO 8601 із часовою зоною
        try:
            return datetime.fromisoformat(dt)
        except Exception:
            # Якщо формат інший, можна додати додаткову логіку
            return None
    return None


def is_match_changed(db_match: dict, new_match: "Match") -> bool:
    """
    Порівнює матч із бази та новий матч.
    Ігнорує різницю у player_ids, бо ми їх не зберігаємо в БД.
    Вважає, що None в новому матчі — це відсутність зміни.
    """

    fields_to_check = ["win_status", "player_ids", "solo_status", "endtime", "duration", "match_mode"]

    for field in fields_to_check:
        db_value = db_match.get(field)
        new_value = getattr(new_match, field)

        # Якщо нове значення None, вважаємо що зміни нема
        if new_value is None:
            continue

        if field == "endtime":
            db_dt = parse_datetime(db_value)
            new_dt = new_value if isinstance(new_value, datetime) else parse_datetime(new_value)
            if db_dt is None or new_dt is None:
                # Якщо не можемо порівняти - вважаємо що зміни є
                return True
            if db_dt.timestamp() != new_dt.timestamp():
                return True
        else:
            if db_value != new_value:
                return True
    return False


async def fetch_and_log_matches_for_last_day(channel_id: str, days: int = 1):
    """
    Отримує нові матчі за останні `days` днів для всіх гравців каналу
    і записує їх у Supabase.
    """
    # 1. Беремо гравців тільки цього каналу
    players = await get_channel_players(channel_id)
    known_ids = [p.steam_id for p in players]

    # 2. Беремо вже залоговані матчі
    logged_matches = await get_logged_matches()
    logged_ids_set = {m["match_id"] for m in logged_matches}
    print(f"Checking {days} days...")
    print(f"📦 Loaded {len(logged_ids_set)} existing matches from DB")

    match_dict = {}

    # 3. Для кожного гравця тягнемо матчі
    for player in players:
        steam_id = player.steam_id
        print(f"🔍 Fetching matches for {player.name.get("telegram")}")

        raw_matches = await Match.get_recent_matches(steam_id, days=days)
        if not raw_matches:
            continue

        for raw in raw_matches:
            match_id = raw["match_id"]

            # Фільтр по даті
            end_time = get_match_end_time(raw)
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            """print(f"[DEBUG] {match_id=} {end_time=} cutoff={cutoff_time}")"""
            if end_time < cutoff_time:
                continue

            # Якщо вже в словнику, просто додаємо гравця
            if match_id in match_dict:
                if steam_id not in match_dict[match_id].player_ids:
                    match_dict[match_id].player_ids.append(steam_id)
                continue

            # Фільтр тільки на наших гравців
            raw_players = raw.get("players", [])
            match_player_ids = [
                p.get("account_id") for p in raw_players
                if p.get("account_id") in known_ids
            ] or [steam_id]

            # Solo-check
            solo_status = await is_player_solo_in_match(match_id, steam_id)

            # Запис матчу
            match_dict[match_id] = Match(
                match_id=match_id,
                player_ids=match_player_ids,
                win_status=player_win(raw),
                solo_status=solo_status,
                endtime=end_time,
                duration=raw.get("duration", 0),
                match_mode=raw.get("game_mode", 0)
            )

    # 4. Розділяємо на нові та існуючі
    new_matches = []
    updated_matches = []

    for match_id, match in match_dict.items():
        if match_id not in logged_ids_set:
            new_matches.append(match)
        else:
            db_match = next((m for m in logged_matches if m["match_id"] == match_id), None)
            if db_match and is_match_changed(db_match, match):
                updated_matches.append(match)

    # 5. Пишемо в базу
    if new_matches:
        print(f"🆕 Adding {len(new_matches)} new matches...")
        await add_matches(new_matches)

    for match in updated_matches:
        print(f"♻️ Updating match {match.match_id}...")
        await update_match(match)

    print(f"✅ Done! Added {len(new_matches)}, updated {len(updated_matches)} matches.")
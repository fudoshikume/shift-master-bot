import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import List
from shift_master import Player
from match_stats import Match

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def get_channels():
    try:
        response = supabase.table("channels").select("id").execute()
        if response.data is None:
            print("Error fetching channels or no data returned")
            return []
        return [item["id"] for item in response.data]
    except Exception as e:
        print("Exception in get_channels:", e)
        return []

def channel_exists(chat_id):
    response = supabase.table("channels").select("id").execute()
    print(f"DEBUG: response - {response.data}, chat_id - {chat_id}")
    if response.data is None:
        print("Error fetching channels or no data returned")
        return False
    for item in response.data:
        # приводимо до одного типу для порівняння
        if str(item["id"]) == str(chat_id):
            print(f"DEBUG: equality is True")
            return True
        else:
            print(f"DEBUG: equality is False")
    return False

async def add_channel(chat_id, chat_name, permissions=None):
    if permissions is None:
        permissions = {}

    now_utc = datetime.now(timezone.utc).isoformat()

    response = supabase.table("channels").insert({
        "id": chat_id,
        "name": chat_name,
        "permissions": permissions,
        "joined_at": now_utc
    }).execute()

    if response.error or response.data is None:
        print(f"Error inserting channel: {response.error}")
        return False
    return True

def get_players():
    response = supabase.table("players").select("*").execute()
    players = []
    for p in response.data:
        # припустимо, що p['name'] збережено як json-рядок або dict
        name_dict = p.get("name")
        if isinstance(name_dict, str):
            import json
            name_dict = json.loads(name_dict)
        player = Player(steam_id=p["steam_id"], name=name_dict)
        player.current_rank = p.get("current_rank", 0)
        # Додаткові поля якщо є
        players.append(player)

    return players

async def get_channel_players(channel_id: str) -> list[Player]:
    # 1. Дістаємо steam_id з player_channels
    res_ids = supabase.table("player_channels").select("steam_id").eq("channel_id", channel_id).execute()
    if res_ids is None:
        print("No data in Player_channels table")
        return []

    steam_ids = [item["steam_id"] for item in res_ids.data]
    if not steam_ids:
        return []

    # 2. Дістаємо повних гравців за steam_id
    res_players = supabase.table("players").select("*").in_("steam_id", steam_ids).execute()
    if res_players.data is None:
        print("No data in Players table")
        return []

    # 3. Конвертуємо в список Player
    players = []
    for p in res_players.data:
        # припустимо, що p['name'] збережено як json-рядок або dict
        name_dict = p.get("name")
        if isinstance(name_dict, str):
            import json
            name_dict = json.loads(name_dict)
        player = Player(steam_id=p["steam_id"], name=name_dict)
        player.current_rank = p.get("current_rank", 0)
        # Додаткові поля якщо є
        players.append(player)

    return players

def add_player(player_data: dict):
    # Додаємо гравця в players
    res = supabase.table("players").insert(player_data).execute()
    if res.data is None:  # 201 Created
        print("Error inserting player data")
        return False

    # Додаємо зв'язки в player_channels, якщо є channel_ids у player_data
    if "channel_ids" in player_data:
        channel_ids = player_data["channel_ids"]
        if isinstance(channel_ids, str):
            channel_ids = [channel_ids]  # якщо один канал, зробимо список

        for ch_id in channel_ids:
            supabase.table("player_channels").insert({
                "steam_id": player_data["steam_id"],
                "channel_id": ch_id
            }).execute()
    return True

def update_player(player_id, updates: dict):
    supabase.table("players").update(updates).eq("steam_id", player_id).execute()

def remove_player(steam_id: int, channel_id: str = None):
    """
    Якщо channel_id заданий - тільки зняти зв'язок у player_channels,
    якщо ні - повністю видалити гравця і всі зв'язки.
    """
    if channel_id:
        # Видаляємо зв'язок з конкретним каналом
        supabase.table("player_channels") \
            .delete() \
            .eq("steam_id", steam_id) \
            .eq("channel_id", channel_id) \
            .execute()

        # Перевіряємо, чи залишились ще зв'язки для цього гравця
        res = supabase.table("player_channels") \
            .select("channel_id") \
            .eq("steam_id", steam_id) \
            .execute()
        if not res.data:
            # Якщо зв'язків нема - видаляємо гравця повністю
            supabase.table("players").delete().eq("steam_id", steam_id).execute()

    else:
        # Видаляємо гравця повністю разом зі зв'язками
        supabase.table("player_channels").delete().eq("steam_id", steam_id).execute()
        supabase.table("players").delete().eq("steam_id", steam_id).execute()

async def get_logged_matches(limit=2000, chunk_size=1000):
    """
    Отримує останні матчі з matchlog, гарантовано враховуючи більше 1000 записів.
    limit - загальна кількість останніх матчів для вибірки
    chunk_size - кількість записів у кожному запиті
    """
    matches = []
    start = 0
    while start < limit:
        end = start + chunk_size - 1
        res = supabase.table("matchlog") \
            .select("*") \
            .order("endtime", desc=True) \
            .range(start, end) \
            .execute()
        data = res.data or []
        if not data:
            break
        matches.extend(data)
        if len(data) < chunk_size:
            break
        start += chunk_size

    print(f"DEBUG: Total matches fetched (paginated): {len(matches)}")
    return matches[:limit]

async def get_logged_match_objects():
    raw_matches = await get_logged_matches()
    match_ids = [m["match_id"] for m in raw_matches]

    print(f"DEBUG: Total matches fetched: {len(raw_matches)}")

    # Запит гравців за всіма матчами разом
    players_data = await get_all_match_players(match_ids)

    print(f"DEBUG: Total match_players rows fetched: {len(players_data)}")

    # Групуємо гравців за match_id
    players_by_match = {}
    for pd in players_data:
        players_by_match.setdefault(pd["match_id"], []).append(pd["steam_id"])

    matches = []
    empty_player_ids = 0
    for m in raw_matches:
        print(f"[RAW MATCH DEBUG] {m['match_id']} | "
              f"endtime={m.get('endtime')} | "
              f"win_status={m.get('win_status')} | "
              f"solo_status={m.get('solo_status')} | "
              f"duration={m.get('duration')} | "
              f"match_mode={m.get('match_mode')}")
        player_ids = players_by_match.get(m["match_id"], [])
        if not player_ids:
            print(f"DEBUG: No players for match_id {m['match_id']}, date {m.get('endtime')}")
            empty_player_ids += 1

        dt_endtime = parse_timestamp(m.get("endtime")) if m.get("endtime") else None

        # 🔎 DEBUG: вивести всі дані по матчу
        # debug_str = " | ".join([
        #     f"match_id={m.get('match_id')}",
        #     f"endtime={m.get('endtime')}",
        #     f"parsed_endtime={dt_endtime}",
        #     f"duration={m.get('duration')}",
        #     f"match_mode={m.get('match_mode')}",
        #     f"win_status={m.get('win_status')}",
        #     f"solo_status={m.get('solo_status')}",
        #     f"player_ids={player_ids}"
        # ])
        # print(f"[MATCH DEBUG] {debug_str}")

        match_obj = Match(
            match_id=m["match_id"],
            win_status=bool(m["win_status"]),
            solo_status=bool(m["solo_status"]) if m.get("solo_status") is not None else None,
            endtime=dt_endtime,
            duration=m.get("duration"),
            match_mode=m.get("match_mode"),
            player_ids=player_ids
        )
        matches.append(match_obj)

    print(f"DEBUG: Matches with empty player_ids: {empty_player_ids}")
    return matches

async def add_matches(matches: List[Match]) -> bool:

    """
    Додає нові матчі у matchlog та match_players.
    """
    if not matches:
        return True

    matchlog_rows = []
    match_players_rows = []

    for m in matches:
        matchlog_rows.append({
            "match_id": m.match_id,
            "player_ids": m.player_ids,  # ✅ додаємо в matchlog
            "win_status": int(m.win_status),
            "solo_status": int(m.solo_status) if m.solo_status is not None else None,
            "endtime": m.endtime.isoformat() if isinstance(m.endtime, datetime) else m.endtime,
            "duration": m.duration,
            "match_mode": m.match_mode
        })

        match_players_rows.extend(
            {"match_id": m.match_id, "steam_id": pid}
            for pid in m.player_ids
        )

    # Запис у matchlog
    res1 = supabase.table("matchlog").upsert(matchlog_rows, on_conflict="match_id").execute()
    if res1.data is None:
        print("❌ Error inserting into matchlog:", res1)
        return False

    # Запис у match_players
    res2 = supabase.table("match_players").upsert(match_players_rows).execute()
    if res2.data is None:
        print("❌ Error inserting into match_players:", res2)
        return False

    print(f"✅ Added {len(matches)} matches to DB")
    return True

async def update_match(match: Match) -> bool:
    """
    Оновлює дані матчу в matchlog та синхронізує match_players.
    """
    res1 = supabase.table("matchlog").update({
        "player_ids": match.player_ids,  # ✅ оновлюємо тут теж
        "win_status": int(match.win_status),
        "solo_status": int(match.solo_status) if match.solo_status is not None else None,
        "endtime": match.endtime.isoformat() if isinstance(match.endtime, datetime) else match.endtime,
        "duration": match.duration,
        "match_mode": match.match_mode
    }).eq("match_id", match.match_id).execute()

    if res1.data is None:
        print(f"❌ Error updating matchlog for {match.match_id}: {res1}")
        return False

    # Видаляємо старі зв’язки гравців
    supabase.table("match_players").delete().eq("match_id", match.match_id).execute()

    # Додаємо актуальні
    match_players_rows = [
        {"match_id": match.match_id, "steam_id": pid}
        for pid in match.player_ids
    ]
    res2 = supabase.table("match_players").insert(match_players_rows).execute()

    if res2.data is None:
        print(f"❌ Error updating match_players for {match.match_id}: {res2}")
        return False

    print(f"♻️ Updated match {match.match_id}")
    return True

#misc for db operating
def parse_timestamp(ts_str):
    try:
        # Приклад для формату "2025-04-15 19:09:18+00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None

async def get_all_match_players(match_ids, chunk_size=500):
    if not match_ids:
        return []

    all_players = []

    for i in range(0, len(match_ids), chunk_size):
        chunk = match_ids[i:i + chunk_size]

        res = (
            supabase.table("match_players")
            .select("match_id, steam_id")
            .in_("match_id", chunk)
            .execute()
        )

        all_players.extend(res.data or [])

    return all_players
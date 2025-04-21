import asyncio
from core import get_match_end_time, player_win

async def fetch_and_log_matches_for_last_day(days: int):
    from match_stats import Match
    from shift_master import load_players_from_csv
    from core import player_win, get_match_end_time

    players = load_players_from_csv()
    existing_matches = Match.read_matches_from_csv()
    existing_ids = {m.match_id for m in existing_matches}
    print(f"📦 Loaded {len(existing_ids)} existing match IDs")

    match_dict = {}

    for player in players:
        print(f"🔍 Fetching for {player.name.get('telegram', str(player.steam_id))}")
        raw_matches = await Match.get_recent_matches(player.steam_id, days=days)

        if not raw_matches:
            continue

        for raw in raw_matches:
            match_id = raw["match_id"]

            if match_id in existing_ids:
                # Already stored permanently — skip
                continue

            steam_id = player.steam_id

            if match_id not in match_dict:
                match = Match(
                    match_id=match_id,
                    player_ids=[steam_id],
                    win_status=player_win(raw),
                    solo_status=raw.get("party_size") == 1,
                    endtime=get_match_end_time(raw),
                    duration=raw.get("duration", 0)
                )
                match_dict[match_id] = match
            else:
                # Only happens if another known player saw the same match
                if steam_id not in match_dict[match_id].player_ids:
                    match_dict[match_id].player_ids.append(steam_id)

    # Only now add to known match IDs
    new_matches = list(match_dict.values())
    print(f"✅ Found {len(new_matches)} new matches")

    if new_matches:
        Match.write_matches_to_csv(new_matches)
        print(f"📝 matchlog.csv updated!")
    else:
        print("📭 No new matches to write.")

# Run it
asyncio.run(fetch_and_log_matches_for_last_day())
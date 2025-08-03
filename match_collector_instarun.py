import asyncio

async def fetch_and_log_matches_for_last_day(days: int):
    from match_stats import Match, is_player_solo_in_match, read_matches_from_csv
    from shift_master import load_players_from_csv
    from core import player_win, get_match_end_time

    players = load_players_from_csv()
    existing_matches = read_matches_from_csv()
    existing_dict = {m.match_id: m for m in existing_matches}
    print(f"📦 Loaded {len(existing_dict)} existing matches")

    updated_matches = []
    match_dict = {}

    known_ids = [p.steam_id for p in players]

    for player in players:
        print(f"🔍 Fetching for {player.name.get('telegram', str(player.steam_id))}")
        raw_matches = await Match.get_recent_matches(player.steam_id)

        if not raw_matches:
            continue

        for raw in raw_matches:
            match_id = raw["match_id"]
            steam_id = player.steam_id

            # Avoid reprocessing same match_id
            if match_id in match_dict:
                if steam_id not in match_dict[match_id].player_ids:
                    match_dict[match_id].player_ids.append(steam_id)
                continue

            # Collect player IDs in match
            raw_players = raw.get("players", [])
            match_player_ids = [p.get("account_id") for p in raw_players if p.get("account_id") in known_ids]
            if not match_player_ids:
                match_player_ids = [steam_id]

            # Get updated game mode and solo status
            match_mode = raw.get("game_mode", 0)  # default to 0 (Unknown) if missing

            existing = existing_dict.get(match_id)
            # If already marked as solo, don't re-check
            if existing and existing.solo_status == 1:
                solo_status = 1
            else:
                solo_status = await is_player_solo_in_match(match_id, steam_id)

            match = Match(
                match_id=match_id,
                player_ids=match_player_ids,
                win_status=player_win(raw),
                solo_status=solo_status,
                endtime=get_match_end_time(raw),
                duration=raw.get("duration", 0),
                match_mode=match_mode
            )
            match_dict[match_id] = match

    for match_id, match in match_dict.items():
        existing = existing_dict.get(match_id)
        if not existing:
            updated_matches.append(match)
        elif match != existing:  # If anything differs, we re-save it
            print(f"♻️ Updating match {match_id}")
            updated_matches.append(match)
        else:
            print(f"⏩ Skipping unchanged match {match_id}")

    print(f"✅ {len(updated_matches)} matches to write")

    for match in updated_matches:
        existing_dict[match.match_id] = match

    Match.write_matches_to_csv(list(existing_dict.values()), overwrite=True)
    print(f"📝 matchlog.csv updated with {len(existing_dict)} total entries!")

# Run it
asyncio.run(fetch_and_log_matches_for_last_day(days=7))
import asyncio

async def fetch_and_log_matches_for_last_day(days: int):
    from match_stats import Match
    from shift_master import load_players_from_csv
    from core import player_win, get_match_end_time

    players = load_players_from_csv()
    existing_matches = Match.read_matches_from_csv()
    existing_dict = {m.match_id: m for m in existing_matches}
    print(f"📦 Loaded {len(existing_dict)} existing matches")

    updated_matches = []
    match_dict = {}

    known_ids = [p.steam_id for p in players]

    for player in players:
        print(f"🔍 Fetching for {player.name.get('telegram', str(player.steam_id))}")
        raw_matches = await Match.get_recent_matches(player.steam_id, days=days)

        if not raw_matches:
            continue

        for raw in raw_matches:
            print(raw)
            match_id = raw["match_id"]
            steam_id = player.steam_id
            is_parsed = raw.get("version") is not None

            # Skip if match already exists and hasn't changed
            if match_id in match_dict:
                # Ensure we add the player to the player_ids list if they aren't already present
                if steam_id not in match_dict[match_id].player_ids:
                    match_dict[match_id].player_ids.append(steam_id)
                continue

            # Include all known players in this match
            raw_players = raw.get("players", [])
            match_player_ids = [p.get("account_id") for p in raw_players if p.get("account_id") in known_ids]

            # Add the current player's steam_id if no known players are found
            if not match_player_ids:
                match_player_ids = [steam_id]

            match = Match(
                match_id=match_id,
                player_ids=match_player_ids,
                win_status=player_win(raw),
                solo_status=raw.get("party_size") == 1,
                endtime=get_match_end_time(raw),
                duration=raw.get("duration", 0),
                is_parsed=is_parsed
            )
            match_dict[match_id] = match

    # Decide what to update
    for match_id, match in match_dict.items():
        existing = existing_dict.get(match_id)

        if not existing:
            updated_matches.append(match)
        elif not existing.is_parsed and match.is_parsed:
            print(f"♻️ Match {match_id} is now parsed — updating it")
            updated_matches.append(match)
        else:
            print(f"⏩ Match {match_id} already up to date")

    print(f"✅ {len(updated_matches)} matches to write (new or re-parsed)")

    # Merge updated + existing into one dict
    for match in updated_matches:
        existing_dict[match.match_id] = match  # Replace or add

    # Write full list back
    Match.write_matches_to_csv(list(existing_dict.values()), overwrite=True)
    print(f"📝 matchlog.csv updated with {len(existing_dict)} total entries!")

# Run it
asyncio.run(fetch_and_log_matches_for_last_day(days=1))
import aiohttp
import asyncio
import db
from core import get_accusative_case, day_cases

async def get_matches(session, steam_id, days):
    """Returns JSON of a player's recent matches."""
    url = f'https://api.opendota.com/api/players/{steam_id}/matches'
    params = {"date": days}  # Fetch matches based on the 'days' parameter
    async with session.get(url, params=params) as response:
        if response.status != 200:
            print(f"[Error] Failed to fetch matches for {steam_id}")
            return []
        matches = await response.json()
        print(f"[OK] Fetched {len(matches)} matches for {steam_id}")
        return matches

async def request_parse(session, match_id):
    """Requests OpenDota to parse a given match."""
    url = f'https://api.opendota.com/api/request/{match_id}'
    async with session.post(url) as response:
        if response.status == 200:
            print(f"[Parse Requested] Match {match_id}")
        else:
            print(f"[Failed] Could not request parse for {match_id}")
        return await response.json()

async def check_and_parse_matches(days, send_message_callback=None):
    print(f"\n[Start] Checking matches to parse from the last {days} days...")
    players = await db.get_players()
    async with aiohttp.ClientSession() as session:
        tasks = [get_matches(session, player.steam_id, days) for player in players]
        results = await asyncio.gather(*tasks)

        parse_tasks = []
        for matches in results:
            for match in matches:
                if match.get("version") is None:  # Unparsed game
                    parse_tasks.append(request_parse(session, match["match_id"]))

        if parse_tasks:
            await asyncio.gather(*parse_tasks)
        else:
            print("[Done] No matches needed parsing.")

    if send_message_callback:
        await send_message_callback(f"[Готово] Пропарсив вам матчі за {days} {get_accusative_case(days, day_cases)}.")

async def run_loop(days=7, send_message_callback=None):
    while True:
        try:
            await check_and_parse_matches(days, send_message_callback)
        except Exception as e:
            print(f"[Crash] Error during parse check: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    print("[Run] Parser is starting...")
    asyncio.run(run_loop())

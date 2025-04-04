from typing import Any
import requests
import datetime
import aiohttp
import asyncio
from django.db.models.query_utils import select_related_descend
#import schedule
from telegram import Bot
from datetime import datetime, timedelta
import shift_master
from shift_master import Player, players


async def get_matches(session, steam_id):
    """returns json view of player's recent matches"""
    url = f'https://api.opendota.com/api/players/{steam_id}/Matches'
    limit = {"date": 1}
    response = requests.get(url, params=limit)

    if response.status_code != 200:
        print("Error fetching data from OpenDota API.")
        return None
    matches = response.json()
    return matches

async def request_parse(session, match_id):
    url_for_parse = f'https://api.opendota.com/api/request/{match_id}'
    async with session.post(url_for_parse) as response:
        return response.json

async def check_and_parse_matches():
    async with aiohttp.ClientSession() as session:
        tasks = [get_matches(session, player.steam_id) for player in players]
        results = await asyncio.gather(*tasks)

        parse_tasks = []
        for matches in results:
            for match in matches:
                if match.get("version") is None:  # Unparsed game
                    parse_tasks.append(request_parse(session, match["match_id"]))

        if parse_tasks:
            await asyncio.gather(*parse_tasks)
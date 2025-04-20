from datetime import datetime, timedelta, timezone

names = ['Братішка', 'Старий', 'Муркотик', 'Єбака', 'Батя']

def player_win(match_json: dict) -> bool:
    """Returns True if the player won the match."""
    is_radiant = match_json.get("player_slot", 0) < 128
    return is_radiant == match_json.get("radiant_win", False)


def get_match_end_time(match) -> datetime:
    match_start_game = datetime.fromtimestamp(match['start_time'], tz=timezone.utc)
    match_duration = timedelta(seconds=match['duration'])
    return match_start_game + match_duration
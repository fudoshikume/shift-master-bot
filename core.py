from datetime import datetime, timedelta, timezone

names = ['Братішка', 'Старий', 'Муркотик', 'Єбака', 'Батя']
day_cases = ('добу','доби','діб')

def player_win(match_json: dict) -> bool:
    """Returns True if the player won the match."""
    is_radiant = match_json.get("player_slot", 0) < 128
    return is_radiant == match_json.get("radiant_win", False)


def get_match_end_time(match) -> datetime:
    match_start_game = datetime.fromtimestamp(match['start_time'], tz=timezone.utc)
    match_duration = timedelta(seconds=match['duration'])
    return match_start_game + match_duration

def get_accusative_case(number: int, word_forms: tuple[str, str, str]) -> str:
    if 11 <= number % 100 <= 14:
        return word_forms[2]
    elif number % 10 == 1:
        return word_forms[0]
    elif 2 <= number % 10 <= 4:
        return word_forms[1]
    else:
        return word_forms[2]
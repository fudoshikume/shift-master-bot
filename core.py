from datetime import datetime, timedelta, timezone

names = ['Братішка', 'Старий', 'Муркотик', 'Єбака', 'Батя']
day_cases = ('добу','доби','діб')

rank_id_to_tier = {
    11: "Герольд I (Herald I)",
    12: "Герольд II (Herald II)",
    13: "Герольд III (Herald III)",
    14: "Герольд IV (Herald IV)",
    15: "Герольд V (Herald V)",
    21: "Вартовий I (Guardian I)",
    22: "Вартовий II (Guardian II)",
    23: "Вартовий III (Guardian III)",
    24: "Вартовий IV (Guardian IV)",
    25: "Вартовий V (Guardian V)",
    31: "Лицар I (Crusader I)",
    32: "Лицар II (Crusader II)",
    33: "Лицар III (Crusader III)",
    34: "Лицар IV (Crusader IV)",
    35: "Лицар V (Crusader V)",
    41: "Архонт I (Archon I)",
    42: "Архонт II (Archon II)",
    43: "Архонт III (Archon III)",
    44: "Архонт IV (Archon IV)",
    45: "Архонт V (Archon V)",
    51: "Легенда I (Legend I)",
    52: "Легенда II (Legend II)",
    53: "Легенда III (Legend III)",
    54: "Легенда IV (Legend IV)",
    55: "Легенда V (Legend V)",
    61: "Древній I (Ancient I)",
    62: "Древній II (Ancient II)",
    63: "Древній III (Ancient III)",
    64: "Древній IV (Ancient IV)",
    65: "Древній V (Ancient V)",
    71: "Божественний I (Divine I)",
    72: "Божественний II (Divine II)",
    73: "Божественний III (Divine III)",
    74: "Божественний IV (Divine IV)",
    75: "Божественний V (Divine V)",
    80: "Безсмертний (Immortal)",
    0: "Ранг невідомий (Unranked)"
}

GAME_MODES = {
    0: "Unknown",
    1: "All Pick",
    2: "Captains Mode",
    3: "Random Draft",
    4: "Single Draft",
    5: "All Random",
    6: "Intro",
    7: "Diretide",
    8: "Reverse Captains Mode",
    9: "Greeviling",
    10: "Tutorial",
    11: "Mid Only",
    12: "Least Played",
    13: "Limited Heroes",
    14: "Compendium Matchmaking",
    15: "Custom",
    16: "Captains Draft",
    17: "Balanced Draft",
    18: "Ability Draft",
    19: "Event",
    20: "AR Death Match",
    21: "1v1 Mid",
    22: "All Draft",
    23: "Turbo",
    24: "Mutation",
    25: "Coaches Challenge",
}

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
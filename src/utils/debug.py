import json
from datetime import datetime
from utils.states import PlayerState

DEBUG_PLAYERS_PATH = "./data/debug/players.json"

def parse_starttime(value, fallback=None):
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return fallback or datetime.now()

def load_debug_player_state(player_number: int) -> PlayerState:
    with open(DEBUG_PLAYERS_PATH, "r") as f:
        players = json.load(f)

    human_players = [p for p in players if p["is_human"]]
    current = human_players[player_number]

    # Check for existing timekeeper
    existing_timekeeper = next((p for p in players if p.get("timekeeper", False)), None)
    now = datetime.now()

    if not existing_timekeeper:
        # Set this player as timekeeper
        current["timekeeper"] = True
        current["starttime"] = now.isoformat()
        print(f"[DEBUG] Setting player {current['code_name']} as TIMEKEEPER")

        # Write updated players.json
        for i, p in enumerate(players):
            if p["code_name"] == current["code_name"]:
                players[i] = current
        with open(DEBUG_PLAYERS_PATH, "w") as f:
            json.dump(players, f, indent=2)

    else:
        # Use existing timekeeper's starttime
        current["timekeeper"] = False
        current["starttime"] = existing_timekeeper["starttime"]

    current["starttime"] = parse_starttime(current["starttime"])
    return PlayerState(**current)

def load_debug_players(debug_folder: str) -> list[PlayerState]:
    with open(f"{debug_folder}/players.json", "r") as f:
        raw_players = json.load(f)

    now = datetime.now()

    # Get timekeeper's starttime
    timekeeper = next((p for p in raw_players if p.get("timekeeper", False)), None)
    shared_start = parse_starttime(timekeeper["starttime"]) if timekeeper else now

    players = []
    for p in raw_players:
        p["starttime"] = parse_starttime(p.get("starttime", ""), fallback=shared_start)
        players.append(PlayerState(**p))
    return players

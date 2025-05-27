import json, os, shutil
from time import sleep
from datetime import datetime
from colorama import Fore, Style
from utils.states import GameState, PlayerState, ScreenEnum
from utils.logging_utils import MasterLogger
from utils.chatbot.ai_v5 import AIPlayer
from utils.file_io import (
    load_players_from_lobby, 
    save_player_to_lobby_file, 
    synchronize_start_time
)
from utils.constants import COLOR_DICT

TEMPLATE_BASE = "./data/debug/templates"
DEBUG_LOBBY_BASE = "./data/debug/lobbies"

def get_next_lobby_id() -> int:
    """
    Scans the debug lobby directory and determines the next available lobby ID.

    Returns:
        int: The next sequential lobby ID based on existing 'lobby_x' folders.
    """

    existing = [int(d.split("_")[-1]) for d in os.listdir(DEBUG_LOBBY_BASE) if d.startswith("lobby_")]
    return max(existing, default=-1) + 1

def create_lobby_dir(lobby_id: int) -> str:
    """
    Creates a new directory for the specified debug lobby ID.

    Args:
        lobby_id (int): The ID of the lobby to create.

    Returns:
        str: The full path to the created lobby directory.
    """
    lobby_path = os.path.join(DEBUG_LOBBY_BASE, f"lobby_{lobby_id}")
    os.makedirs(lobby_path, exist_ok=True)
    return lobby_path

def debug_setup(ss: ScreenEnum, gs: GameState, ps: PlayerState, template_folder: str, player_number: int) -> tuple:
    """
    Initializes the debug setup for a single player using pre-defined template data.

    This function loads a specific player's data from a debug template, assigns them a code name and color,
    sets up a file-based lobby environment (including chat, voting, and start time files), and
    initializes both the player and their AI doppelgänger. The timekeeper is responsible for creating
    the lobby and synchronizing the start time, while other players wait for setup to complete.

    Args:
        ss (ScreenEnum): The current screen state (unused but included for consistency).
        gs (GameState): The shared game state object to be updated with player and lobby data.
        ps (PlayerState): The player's state object, to be populated with template data.
        template_folder (str): The name of the debug template folder to load player data from.
        player_number (int): The index of the player within the template file.

    Returns:
        tuple: A tuple of (ScreenEnum.CHAT, updated GameState, initialized PlayerState)
    """

    logger = MasterLogger.get_instance()

    # Load template data
    with open(os.path.join(TEMPLATE_BASE, template_folder, "players.json")) as f:
        all_players = json.load(f)
    player_data = all_players[player_number]

    # Timekeeper setup
    is_timekeeper = player_number == 0
    if is_timekeeper:
        lobby_id = get_next_lobby_id()
        lobby_path = create_lobby_dir(lobby_id)
        # Optionally clear old contents
        for fname in os.listdir(lobby_path):
            os.remove(os.path.join(lobby_path, fname))
        print(Fore.GREEN + f"[DEBUG] Timekeeper creating lobby_{lobby_id}" + Style.RESET_ALL)
    else:
        # Wait for timekeeper to create lobby
        while True:
            lobby_ids = sorted([int(d.split("_")[-1]) for d in os.listdir(DEBUG_LOBBY_BASE) if d.startswith("lobby_")])
            if lobby_ids:
                lobby_id = max(lobby_ids)
                lobby_path = os.path.join(DEBUG_LOBBY_BASE, f"lobby_{lobby_id}")
                if os.path.exists(os.path.join(lobby_path, "players.json")):
                    break
            sleep(1)

    # Build paths and GameState
    gs.chat_log_path = os.path.join(lobby_path, "chat_log.txt")
    gs.start_time_path = os.path.join(lobby_path, "starttime.txt")
    gs.voting_path = os.path.join(lobby_path, "voting.json")
    gs.player_path = os.path.join(lobby_path, "players.json")
    gs.number_of_human_players = len(all_players)

    # Create PlayerState
    ps = PlayerState(
        lobby_id=0,
        first_name=player_data["first_name"],
        last_initial=player_data["last_initial"],
        code_name=player_data["code_name"],
        grade=str(player_data["grade"]),
        favorite_food=player_data["favorite_food"],
        favorite_animal=player_data["favorite_animal"],
        hobby=player_data["hobby"],
        extra_info=player_data["extra_info"],
        is_human=True,
        color_name=player_data["color_name"],
    )
    ps.logger = logger
    ps.written_to_file = True
    

    # Save players
    save_player_to_lobby_file(ps)
    ps.ai_doppleganger = AIPlayer(player_to_steal=ps)
    save_player_to_lobby_file(ps.ai_doppleganger.player_state)

    # Timekeeper sets start time
    if is_timekeeper:
        synchronize_start_time(gs, ps)
    else:
        # Wait for timekeeper to write start time
        while not os.path.exists(gs.start_time_path):
            sleep(0.5)

    # Load full player list
    gs.players = load_players_from_lobby(gs)
    gs.players = sorted(gs.players, key=lambda p: p.code_name)
    ps.ai_doppleganger.initialize_game_state(gs)

    print(Fore.GREEN + "All players are ready!" + Style.RESET_ALL)
    print(COLOR_DICT[ps.color_name] + f"{ps.code_name} joined the lobby" + Style.RESET_ALL)
    print(COLOR_DICT[ps.ai_doppleganger.player_state.color_name] + f"{ps.ai_doppleganger.player_state.code_name} joined the lobby" + Style.RESET_ALL)
    gs.players.append(ps)
    gs.players.append(ps.ai_doppleganger.player_state)

    input(Fore.MAGENTA + "Press Enter to continue to the chat phase..." + Style.RESET_ALL)
    return ScreenEnum.CHAT, gs, ps

import asyncio
import inspect
import json
import random
import argparse
from utils.debug import load_debug_game_state, load_debug_player_state
from utils.states import PlayerState, ScreenEnum
from setup import collect_player_data
from intro_screen import play_intro
from game_MVP import play_game    # New screen uses curses for separate input spot
# from game_MVP_NEW import play_game
# from fake_chat import play_game # FOR DEBUGGING
from score_NEW import score_screen
import inspect
from voting import voting_round
# import signal

# Importing constants and logging
from utils.constants import BLANK_GS, BLANK_PS, ICEBREAKERS
from utils.logging_utils import MasterLogger

def parse_args():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description="Game setup and execution.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed logging."
    )
    parser.add_argument(
        "--debug_folder",
        type=str,
        default="./data/debug/1_player",
        help="Specify the folder for debug data."
    )
    parser.add_argument(
        "--player_number",
        type=int,
        default=0,
        help="Specify the player number for debugging."
    )
    return parser.parse_args()

async def main():
    args = parse_args()

    master_logger = MasterLogger(
        init=True,
        clear=False,
        log_path="./logs/_master.log"
    )
    master_logger.log("Game started - Initializing master logger")

    # Dictionary mapping game states to their corresponding handler functions.
    state_handler = {
        ScreenEnum.INTRO: play_intro,
        ScreenEnum.SETUP: collect_player_data,
        ScreenEnum.CHAT: play_game,
        ScreenEnum.SCORE: score_screen,
        ScreenEnum.VOTE: voting_round
    }

    # Initialize the starting screen state and blank game/player states.
    if args.debug:
        ss = ScreenEnum.CHAT
        gs = load_debug_game_state(debug_folder=args.debug_folder)
        gs.players = [PlayerState(**p) for p in json.load(open(f'{args.debug_folder}/players.json'))]

        ps = load_debug_player_state(
            debug_folder=args.debug_folder,
            player_number=args.player_number
        )
    else:
        ss = ScreenEnum.INTRO
        gs = BLANK_GS

    icebreakers = ICEBREAKERS[1:]
    first_breaker = ICEBREAKERS[0]
    random.shuffle(icebreakers)
    icebreakers.insert(0, first_breaker)
    gs.icebreakers = ICEBREAKERS
    ps = BLANK_PS

    # Main game loop
    while True:
        # Check if the current screen state has a handler function.
        if ss in state_handler:
            handler = state_handler[ss]
            
            # Determine if the handler is an asynchronous coroutine.
            if inspect.iscoroutinefunction(handler):
                next_state, next_gs, next_ps = await handler(ss, gs, ps)
            else:
                next_state, next_gs, next_ps = handler(ss, gs, ps)
            
            # Update state variables with the results from the handler.
            ss = next_state
            gs = next_gs
            ps = next_ps
            
            # Log the state transition for debugging and tracking.
            master_logger.log(f"Transitioned to state: {ss}")
        else:
            # Handle unexpected or invalid states.
            master_logger.error(f"Invalid game state encountered: {ss}")
            print("Invalid game state")
            break

if __name__ == "__main__":
    # Run the main game loop using asyncio for asynchronous operations.
    asyncio.run(main())

import asyncio
import inspect
import json
import random
import argparse
from debug import debug_setup
from utils.chatbot.ai_v5 import AIPlayer
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
    These command line arguments allow for debugging.

    --debug: Enables debug mode, which skips the intro and setup phases.
    --template_folder: Specifies the folder containing the debug template data.
    --player_number: Indicates which player is using this terminal, useful for multi-player setups.

    So far it only works with 1 player, but it will be extended to support multiple players in the future.
    """
    parser = argparse.ArgumentParser(description="Game setup and execution.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed logging."
    )
    parser.add_argument(
        "--template_folder", type=str, default="1_player",
        help="Name of the debug template folder (e.g., 2_player)"
    )
    parser.add_argument(
        "--player_number", type=int, default=0,
        help="Index of the player using this terminal"
    )
    return parser.parse_args()

async def main():
    '''
    This is the main entry point for the game.

    It initializes the game state, sets up the master logger, and starts the main game loop.
    The game loop handles transitions between different game states, such as the intro screen, player setup, game play, scoring, and voting rounds.
    The game states are managed using a dictionary that maps each state to its corresponding handler function.
    The game can be run in debug mode, which allows for skipping the intro and setup phases and going straight to the chat phase.
    The game state and player state are initialized to blank states, and the icebreakers are shuffled for the game.
    '''
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
        ScreenEnum.DEBUG: debug_setup,
        ScreenEnum.CHAT: play_game,
        ScreenEnum.SCORE: score_screen,
        ScreenEnum.VOTE: voting_round,
    }

    # if debugging set up the game to go straight to the chat phase by going through debug.py
    if args.debug: 
        ss = ScreenEnum.DEBUG
        gs = BLANK_GS
    # Otherwise, play a normal game and start with the intro screen.
    else: 
        ss = ScreenEnum.INTRO
        gs = BLANK_GS

    # grab all icebreakers except for the first one. 
    icebreakers = ICEBREAKERS[1:]
    # grab the first icebreaker (it is the one that asks for players to introduce themselves)
    first_breaker = ICEBREAKERS[0]
    # shuffle the non-first icebreakers to randomize the order of the game.
    random.shuffle(icebreakers)
    # Insert the first icebreaker at the beginning of the list to ensure it is always asked first.
    icebreakers.insert(0, first_breaker)
    gs.icebreakers = icebreakers
    ps = BLANK_PS

    # Main game loop
    while True:
        # make sure the game state is in a valid state
        if ss in state_handler:
            # find out which handler to use based on the current game state
            handler = state_handler[ss]

            # If we're in debug mode and in DEBUG state, we need to pass extra args
            if args.debug and ss == ScreenEnum.DEBUG:
                next_state, next_gs, next_ps = handler(ss, gs, ps, args.template_folder, args.player_number)
            
            # If the handler is a coroutine function, await it to get the next state, game state, and player state.
            elif inspect.iscoroutinefunction(handler):
                next_state, next_gs, next_ps = await handler(ss, gs, ps)

            # If the handler is a regular function, call it to get the next state, game state, and player state.
            else:
                next_state, next_gs, next_ps = handler(ss, gs, ps)

            ss = next_state
            gs = next_gs
            ps = next_ps
            # Log the transition to the next state

            master_logger.log(f"Transitioned to state: {ss}")

        # if the game state is not valid, log an error and break the loop
        else:
            master_logger.error(f"Invalid game state encountered: {ss}")
            print("Invalid game state")
            break


if __name__ == "__main__":
    # Run the main game loop using asyncio for asynchronous operations.
    asyncio.run(main())

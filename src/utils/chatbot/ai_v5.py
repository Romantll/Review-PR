import asyncio
import re
from dataclasses import asdict
import json
from typing import Dict, List, Tuple 
from pydantic import BaseModel
from utils.prompting.prompter import OpenAIPrompter
from . import examples_v4 as ex4
from . import enums_dcs_v3 as dcs3
import sys

from utils.prompting import prompter
sys.path.append("../../")
from utils.states import PlayerState, GameState
from utils.file_io import SequentialAssigner
from utils.constants import (
    NAMES_PATH, NAMES_INDEX_PATH, 
    COLORS_PATH, COLORS_INDEX_PATH
    )
from utils.logging_utils import MasterLogger

import re

def extract_between_delimiters(text: str, delim: str) -> str:
    """
    Extracts the first occurrence of text between two identical delimiters.

    Args:
        text: The full string to search.
        delim: The delimiter used on both sides (e.g., '```').

    Returns:
        The text between the delimiters, or an error message if no match is found.
    """
    pattern = re.escape(delim) + r'(.*?)' + re.escape(delim)
    match = re.search(pattern, text, re.DOTALL)  # DOTALL handles multi-line blocks if needed
    return match.group(1).strip() if match else f"ERROR NO MATCH FOUND ||| DELIM = {delim} ||| TEXT = {text}"

class AIPlayer:
    def __init__(
            self,
            player_to_steal: PlayerState, 
            system_prompt: str = ex4.DEFAULT_SYSTEM_PROMPT,
            debug_bool: bool = False):
        self.humans_messages = []
        self.stolen_player_code_name = player_to_steal.code_name
        self.code_name_assigner = SequentialAssigner(NAMES_PATH, NAMES_INDEX_PATH, "code_names")
        self.color_assigner = SequentialAssigner(COLORS_PATH, COLORS_INDEX_PATH, "colors")
        self.player_state = self._steal_player_state(player_to_steal)
        self.persona = self._build_persona()
        self.system_prompt = system_prompt + json.dumps(asdict(self.player_state))
        self.is_voted_out = False

        self.debug_bool = debug_bool

        # Initialize game state
        self.game_state = None
        self.logger = MasterLogger.get_instance()
        self.logger.info(f"AIPlayer initialized with player: {self.stolen_player_code_name}")
        
        # Prompter Dictionary
        self.prompter_dict = {
            "decide_to_respond": OpenAIPrompter(
                prompt_path="./resources/prompts/v0/decide_to_respond.yaml",
                prompt_headers={
                    "persona": "HERE IS YOUR PERSONA",
                    "minutes": "HERE IS THE CONVERSATION SO FAR",
                },
                temperature=0.01,
                llm_model="gpt-4.1-nano",
            ),
            "respond": OpenAIPrompter(
                prompt_path="./resources/prompts/v0/respond.yaml",
                prompt_headers={
                    "persona": "HERE IS YOUR PERSONA",
                    "minutes": "HERE IS THE CONVERSATION SO FAR",
                    "reasoning": "YOU HAVE DECIDED TO ANSWER FOR THE FOLLOWING REASONIG"
                    },
                temperature=0.5,
                llm_model="gpt-4.1-mini",
            ),
              "stylizer": OpenAIPrompter(
                prompt_path="./resources/prompts/v0/stylizer.yaml",
                prompt_headers={
                    "player_minutes": "HERE ARE MESSAGES THAT YOU WILL COPY THE STYLE FROM",
                    "message": "HERE IS THE MESSAGE YOU WILL STYLIZE",
                },
                temperature=0.01,
                llm_model="gpt-4.1-mini",
            )
        }

    async def decide_to_respond(self, minutes: List[str]) -> Dict[str, str]:
        """Step 1: Decide whether the AI should respond."""

        # Grab the appropriate prompter from the dictionary
        prompter = self.prompter_dict["decide_to_respond"]

        # Define input for the prompt
        input_texts = {
            "persona": self.persona,  
            "minutes": "\n".join(minutes),
        }

        # Get the last message
        last_msg = minutes[-1] if minutes else None

        # Track messages from the original human player to help mimic their style
        if last_msg and last_msg.startswith(f"{self.stolen_player_code_name}:"):
            self.humans_messages.append(last_msg.split(":", 1)[1].strip())

        # Prepare response container
        dtr_resp = {}

        try:
            response_json = await asyncio.to_thread(prompter.get_completion, input_texts)
            resp = response_json[0]
        except Exception as e:
            # raise e
            self.logger.error(f"Error during decision to respond: {e}")
            dtr_resp["decision"] = "ERROR"
            dtr_resp["reasoning"] = f"Error during decision making. {e}"
            return dtr_resp

        decision = extract_between_delimiters(resp, '```')
        reasoning = extract_between_delimiters(resp, '***')

        # Handle result dictionary
        if "ERROR NO MATCH FOUND" not in decision and "ERROR NO MATCH FOUND" not in reasoning:
            dtr_resp["decision"] = decision
            dtr_resp["reasoning"] = reasoning
            self.logger.info(f'DTR DECISION: {dtr_resp["decision"]}')
            self.logger.info(f'DTR REASONING: {dtr_resp["reasoning"]}')

        else:
            dtr_resp["decision"] = "INVALID_FORMAT"
            dtr_resp["reasoning"] = response_json.strip()
            # raise ValueError(f"Invalid format in decision response: {dtr_resp}")
            self.logger.error(f'DTR DECISION: {dtr_resp["decision"]}')
            self.logger.error(f'DTR REASONING: {dtr_resp["reasoning"]}')
        # print(dtr_resp)
        return dtr_resp

    async def respond(self, minutes: List[str], dtr_resp) -> str:
        """Step 3: Generate the response based on the chosen action type."""
        prompter = self.prompter_dict["respond"]
        input_texts = {
            "persona": self.persona, 
            "minutes": "\n".join(minutes),
            "reasoning": dtr_resp["reasoning"]
        }

        error_response = "ERROR"

        try:
            response_json = await asyncio.to_thread(prompter.get_completion, input_texts)
            resp = response_json[0]
        except Exception as e:
            # raise e
            self.logger.error(f"Error during response generation: {e}")
            return error_response

        # Use helper function to extract response between triple backticks
        response = extract_between_delimiters(resp, '```')

        if "ERROR NO MATCH FOUND" in response:
            self.logger.warning(f"Invalid format in response: {resp}")
            return error_response
        else:
            self.logger.info(f"Generated Response: {response}")
            return response

    async def stylize_response(self, response: str) -> str:
        prompter = self.prompter_dict["stylizer"]

        input_texts = {
            "player_minutes": "\n".join(self.humans_messages),
            "response": response
        }
        error_response = "ERROR"

        try:
            # Run the completion in a separate thread to avoid blocking
            raw_response = await asyncio.to_thread(prompter.get_completion, input_texts)
            styled_response = raw_response[0]
            self.logger.info(f"Stylized Response: {styled_response}")
            return styled_response

        except Exception as e:
            # raise e
            self.logger.error(f"Error during stylizing response: {e}")
            return error_response # Fallback response

    def handle_dialogue(self, minutes: List[str]) -> str:
        """Handles a new message by deciding whether to respond and generating a response."""
        # print("inside handle_dialogue")
        # Step 1: Decide whether to respond
        dtr_resp = asyncio.run(
            self.decide_to_respond(minutes)
            )
        # print(dtr_resp)

        # If we decide to stay silent, log the decision and return STAY SILENT
        if dtr_resp["decision"] == "STAY SILENT":
            self.logger.info(f"AI {self.player_state.code_name} decided to stay silent.")
            return "STAY SILENT"
        
        # If we decide to respond, log the decision and procee
        if dtr_resp["decision"] == "RESPOND":
            self.logger.info(f"AI {self.player_state.code_name} decided to respond.")
            
        # Step 2: Generate the response
            response = asyncio.run(
                self.respond(minutes, dtr_resp)
                )
            if response != "ERROR":
                # Step 3: Stylize the response
                styled_response = asyncio.run(
                    self.stylize_response(response)
                    )
                return styled_response
            else:
                return "ERROR"
        else:
            return "No response needed."
    
    def _steal_player_state(self, player_state_to_steal: PlayerState) -> PlayerState:
        """Creates a new player state based on the given one."""
        self.humans_messages.append(player_state_to_steal.extra_info) # use the extra info as a message to mimic style
        return PlayerState(
            first_name=player_state_to_steal.first_name,
            last_initial=player_state_to_steal.last_initial,
            code_name=self.code_name_assigner.assign(),  # Assign a new code name
            color_name=self.color_assigner.assign(),  # Assign a new color name
            grade=player_state_to_steal.grade,
            favorite_food=player_state_to_steal.favorite_food,
            favorite_animal=player_state_to_steal.favorite_animal,
            hobby=player_state_to_steal.hobby,
            extra_info=player_state_to_steal.extra_info,
            written_to_file=True,
            lobby_id=player_state_to_steal.lobby_id,
            is_human=False,  # This player is not human
        )
    
    def _build_persona(self) -> str:
        """Builds the persona for the AI player."""
        player_state = self.player_state
        # Create a persona string based on the player's attributes
        return (
            f"Your name is {player_state.first_name} {player_state.last_initial}. "
            f"You are a {player_state.grade} grader who loves {player_state.favorite_food}, "
            f"{player_state.favorite_animal}, and enjoys {player_state.hobby}. "
            f"One more thing about you: {player_state.extra_info}."
            f"Of course, there is so much more to you than just these things."
        )
   
    def initialize_game_state(self, game_state: GameState):
        """Initialize the game state."""
        self.game_state = game_state
        self.logger.info(f"Game state initialized with players: {self.stolen_player_code_name}")
        self.logger.info(f"Game state: {self.game_state.to_dict()}")

'''
2025-06-08
Author: Dan Schumacher
How to run:
   python ./src/simple_prompt.py
'''
from utils.prompting.prompter import OpenAIPrompter
import json

import argparse
def parse_args():
    parser = argparse.ArgumentParser(description="Simple Prompt Example")
    parser.add_argument(
        "--question",
        type=str,
        default="What is the capital of France?",
        help="Path to the prompt YAML file"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    prompter = OpenAIPrompter(
        prompt_path="./resources/prompts/simple_prompt.yaml",
        prompt_headers={
            "question": "Answer the question according to your persona."
        },       
        temperature=0.0,
    )
    response = prompter.get_completion(
        input_texts={"question": args.question}
    )
    print(f"\n\n{response[0]}\n\n")

if __name__ == "__main__":
    main()
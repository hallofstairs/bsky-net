# %% Imports

import json
import math
import os
from enum import Enum

from openai import OpenAI

from bsky_net import Post
from bsky_net.utils import jsonl

# Constants
EXPERIMENTS_DIR = "../data/experiments"
TEST_SET_PATH = f"{EXPERIMENTS_DIR}/test-set.jsonl"

START_DATE = "2023-05-25"
END_DATE = "2023-05-26"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# %% Define prompts


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Topic:"""


class SystemPrompts(Enum):
    v1 = """"""
    v2 = """"""


# %% Run experiments

EXPERIMENT_NAME = ""

client = OpenAI(api_key=OPENAI_API_KEY)

# Check if folder exists, if exists, raise exception (don't override experiments)
os.mkdir(f"{EXPERIMENTS_DIR}/{EXPERIMENT_NAME}")

for system_prompt in SystemPrompts:
    total_posts = 0

    for post in jsonl[Post].iter(TEST_SET_PATH):
        # Ignore replies (for now)
        if "reply" in post and post["reply"]:
            continue

        # Ignore embeds (for now)
        if "embed" in post and post["embed"]:
            continue

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt.value},
                {"role": "user", "content": make_prompt(post)},
            ],
            logprobs=True,
            temperature=0.0,
        )

        classification = res.choices[0].message.content

        if not classification:
            print("No classification")
            continue

        topic = classification.strip().lower()
        logprobs = res.choices[0].logprobs

        probability = (
            math.exp(logprobs.content[0].logprob)
            if logprobs and logprobs.content
            else -1
        )

        log_entry = {
            "text": post["text"],
            "classification": topic,
            "probability": probability,
            "uri": post["uri"],
        }

        with open(
            f"{EXPERIMENTS_DIR}/{EXPERIMENT_NAME}/{system_prompt.value}.jsonl", "a"
        ) as log_file:
            json.dump(log_entry, log_file)
            log_file.write("\n")

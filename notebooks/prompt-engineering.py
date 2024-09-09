# %% Imports

import json
import math
import os
import typing as t
from collections import Counter
from enum import Enum

from openai import OpenAI

from bsky_net import Post
from bsky_net.utils import jsonl

# Constants
EXPERIMENTS_DIR = "../data/experiments"
TEST_SET_PATH = f"{EXPERIMENTS_DIR}/test-set-v1.jsonl"

START_DATE = "2023-05-25"
END_DATE = "2023-05-26"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# %% Define prompts


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Class:"""


class SystemPrompts(Enum):
    v0 = """On the Bluesky social network, there was a user named Alice that started posting hateful content inside of a long thread called "hellthread". This triggered a conversation about Bluesky's moderation policies. Your goal is to identify any posts that are talking about the Bluesky team's response to the event or their general moderation policies on the platform. If relevant, respond with "1". If not relevant, respond with "0".
"""

    v1 = """On the Bluesky social network, there was a user named Alice that started posting hateful content inside of a long thread called "hellthread". This triggered a conversation about Bluesky's moderation policies. Your goal is to identify any posts that are talking about the Bluesky team's response to the event or their general moderation policies on the platform. If relevant, respond with "1". If not relevant, respond with "0".

Examples:
Text: "This is definitely the answer. Everyone ranting and raving about moderation decisions here are completely blind to how things will work once federation launches."
Class: 1

Text: "Woah this is really smart. I assumed they would drop the invites, but this makes trust and safety easier."
Class: 1

Text: "So wait does "What's Hot Classic" mean the classic feed with nudes or without? Asking for a friend who is in horny jail."
Class: 0"""


class Models(Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_3_5_TURBO = "gpt-3.5-turbo"


class Entry(Post):
    classification: int


class Result(t.TypedDict):
    text: str
    classification: int
    probability: float
    uri: str
    correct: bool


# %% Run experiments


EXPERIMENT_NAME = "first-test"

experiment_dir = f"{EXPERIMENTS_DIR}/{EXPERIMENT_NAME}"
if os.path.exists(experiment_dir):
    raise FileExistsError(f"Experiment directory '{experiment_dir}' already exists!")
os.mkdir(experiment_dir)

client = OpenAI(api_key=OPENAI_API_KEY)

for model in Models:
    for system_prompt in SystemPrompts:
        results = Counter()

        for post in jsonl[Entry].iter(TEST_SET_PATH):
            res = client.chat.completions.create(
                model=model.value,
                messages=[
                    {"role": "system", "content": system_prompt.value},
                    {"role": "user", "content": make_prompt(post)},
                ],
                logprobs=True,
                temperature=0.0,
            )

            classification = res.choices[0].message.content
            logprobs = res.choices[0].logprobs

            if not classification:
                print("No classification")
                continue

            if not logprobs or not logprobs.content:
                raise ValueError("No logprobs")

            pred = int(classification.strip().lower())
            correct = post["classification"] == pred

            log_entry: Result = {
                "text": post["text"],
                "classification": pred,
                "probability": math.exp(logprobs.content[0].logprob),
                "uri": post["uri"],
                "correct": correct,
            }

            if correct:
                if pred == 1:
                    results["tp"] += 1
                else:
                    results["tn"] += 1
            else:
                if pred == 1:
                    results["fp"] += 1
                else:
                    results["fn"] += 1

            results["total"] += 1

            if not correct:
                incorrect_entry = {
                    "text": post["text"],
                    "predicted": pred,
                    "actual": post["classification"],
                    "probability": math.exp(logprobs.content[0].logprob),
                    "uri": post["uri"],
                }
                with open(
                    f"{experiment_dir}/{model.name}-{system_prompt.name}-incorrect.jsonl",
                    "a",
                ) as incorrect_file:
                    json.dump(incorrect_entry, incorrect_file)
                    incorrect_file.write("\n")

            with open(
                f"{experiment_dir}/{model.name}-{system_prompt.name}.jsonl", "a"
            ) as log_file:
                json.dump(log_entry, log_file)
                log_file.write("\n")

        with open(f"{experiment_dir}/results.txt", "a+") as results_file:
            results_file.seek(0, 2)
            if results_file.tell() > 0:
                results_file.write("\n")

            tp = results["tp"]
            tn = results["tn"]
            fp = results["fp"]
            fn = results["fn"]
            total = results["total"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1_score = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0
            )
            accuracy = (tp + tn) / total if total > 0 else 0

            results_file.write(
                f"{model.name} - {system_prompt.name}:\n\n"
                f"TP: {tp:<2} ({tp/total:.2%}) | FP: {fp:<2} ({fp/total:.2%})\n"
                f"FN: {fn:<2} ({fn/total:.2%}) | TN: {tn:<2} ({tn/total:.2%})\n\n"
                f"Precision: {precision:.4f}\n"
                f"Recall:    {recall:.4f}\n"
                f"F1 Score:  {f1_score:.4f}\n"
                f"Accuracy:  {accuracy:.4f}\n"
                f"{'=' * 20}"
            )

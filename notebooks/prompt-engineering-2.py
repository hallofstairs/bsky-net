# %% Imports

import os
import typing as t
from collections import Counter
from enum import Enum

from openai import OpenAI
from pydantic import BaseModel

from bsky_net import Post, jsonl

# Constants
EXPERIMENTS_DIR = "../data/experiments"
TEST_SET_PATH = f"{EXPERIMENTS_DIR}/test-set-v1-sanitized.jsonl"

START_DATE = "2023-05-25"
END_DATE = "2023-05-26"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# %% Prompt helpers

MODEL = "gpt-4o-mini"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

    # sentiment: Sentiment


class UserPrompts:
    v7: str = """{context}
{text}

Which of the following describes the stance of the above post?
A: {stance}
B: {stance}

"""


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Class:"""


# %% Structured output testing

Stance = t.Literal["favor", "against", "none"]


class Topic(str, Enum):
    moderation_policies = (
        "Discussing Bluesky's official rules or policies on content moderation"
    )
    content_removal = "About content being removed or flagged by Bluesky"
    account_removal = (
        "About Bluesky users being suspended or banned, including reasons and appeals"
    )
    trust_and_safety = (
        "Discussions on Bluesky's user safety, harassment, or harmful content"
    )
    transparency = "Expressing concerns or praises about the transparency of Bluesky's moderation decisions"
    algorithmic_moderation = (
        "About AI-based or automated moderation systems used by Bluesky"
    )
    community_moderation = "Discussions about user-driven moderation on Bluesky, like flagging or reporting content"
    moderation_criticism = "Criticizing Bluesky's moderation efforts (e.g., over-enforcement or under-enforcement)"
    moderation_praise = "Commending Bluesky's moderation efforts or improvements"
    general_moderation = "Broad posts about moderation without a specific focus"
    unrelated = "Posts that are not discussing Bluesky's moderation efforts at all."


# Structured output
class StanceDetection(BaseModel):
    topic: list[Topic]
    stance: Stance


SEMEVAL_TRIAL_PATH = "../data/experiments/test-sets/semeval-trial.jsonl"

SemEvalSample = t.TypedDict(
    "SemEvalSample",
    {
        "ID": str,
        "Target": str,
        "Tweet": str,
        "Stance": t.Literal["FAVOR", "AGAINST", "NONE"],
        "Opinion towards": t.Literal["TARGET", "OTHER", "NO_ONE"],
        "Sentiment": t.Literal["POSITIVE", "NEGATIVE", "NEUTRAL"],
    },
)

BSKY_TEST_PATH = "../data/experiments/test-sets/moderation-v1-sanitized.jsonl"


class BskySample(Post):
    classification: t.Literal[0, 1]


results = Counter()

# for sample in jsonl[SemEvalSample].iter(SEMEVAL_TRIAL_PATH):
for sample in jsonl[BskySample].iter(BSKY_TEST_PATH):
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Determine the topic of the user's Bluesky post and their stance on it.",
            },
            {"role": "user", "content": sample["text"]},
        ],
        response_format=StanceDetection,
    )

    stance = completion.choices[0].message.parsed

    if not stance:
        continue

    # print(stance.model_dump())
    print("TEXT: ", sample["text"])

    # if (
    #     stance.topic != sample["Target"].lower()
    #     and sample["Opinion towards"] == "TARGET"
    # ):
    #     print("Topic mismatch", stance.topic, sample["Target"])

    # elif stance.stance != sample["Stance"].lower():
    #     print("Stance mismatch", stance.stance, sample["Stance"])

    # else:
    #     print("Match!")

    if Topic.unrelated in stance.topic and sample["classification"] == 1:
        print("FALSE NEGATIVE", stance.topic, sample["classification"])
        results["fn"] += 1

    elif Topic.unrelated not in stance.topic and sample["classification"] == 0:
        print("FALSE POSITIVE", stance.topic, sample["classification"])
        results["fp"] += 1

    elif Topic.unrelated in stance.topic and sample["classification"] == 0:
        print("TRUE NEGATIVE", stance.topic, sample["classification"])
        results["tn"] += 1

    elif Topic.unrelated not in stance.topic and sample["classification"] == 1:
        print("TRUE POSITIVE", stance.topic, sample["classification"])
        results["tp"] += 1

    print()

tp = results["tp"]
tn = results["tn"]
fp = results["fp"]
fn = results["fn"]
total = tp + tn + fp + fn

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1_score = (
    2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
)
accuracy = (tp + tn) / total if total > 0 else 0

print(
    f"TP: {tp:<2} ({tp/total:.2%}) | FP: {fp:<2} ({fp/total:.2%})\n"
    f"FN: {fn:<2} ({fn/total:.2%}) | TN: {tn:<2} ({tn/total:.2%})\n\n"
    f"Precision: {precision:.4f}\n"
    f"Recall:    {recall:.4f}\n"
    f"F1 Score:  {f1_score:.4f}\n"
    f"Accuracy:  {accuracy:.4f}\n"
    f"{'=' * 20}"
)

# %%

"""
No system prompt:

Precision: 0.7528
Recall:    0.9437
F1 Score:  0.8375
Accuracy:  0.7679
"""

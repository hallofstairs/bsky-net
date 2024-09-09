import json
import os

from bsky_net import Post, records

# Constants
STREAM_DIR = "../data/raw/stream-2023-07-01"
BATCH_DIR = "../data/batches"

BATCH_MAX_N = 50_000
BATCH_QUEUE_MAX_TOKENS = 1_900_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 174
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

SYS_PROMPT = """You are tasked with analyzing a post from the social network Bluesky to determine if it references the network's moderation policies, especially in relation to the Bluesky development team.

Examples:
Text: "This is definitely the answer. Everyone ranting and raving about moderation decisions here are completely blind to how things will work once federation launches."
Class: 1

Text: "I've seen that Alice chick 4 times now. \n\nJust bury her and block. I thought that was the plan here"
Class: 1

Text: "I think I\u2019ve been on here a month with zero invite codes bluesky mods hate me"
Class: 0

Text: "So wait does "What's Hot Classic" mean the classic feed with nudes or without? Asking for a friend who is in horny jail."
Class: 0"""


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Class:"""


# Create BatchAPI request
BATCH_DESCRIPTION = "moderation-2023-05-24_2023-05-28"

START_DATE = "2023-05-24"
END_DATE = "2023-05-28"

if os.path.exists(f"{BATCH_DIR}/{BATCH_DESCRIPTION}"):
    raise ValueError(f"Batch folder '{BATCH_DESCRIPTION}' already exists.")

os.makedirs(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/in")
os.makedirs(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out")

i = 0
batch_size = 0
total_tokens = 0

# Create a file for each batch of posts
for record in records(stream_dir=STREAM_DIR, start_date=START_DATE, end_date=END_DATE):
    if record["$type"] == "app.bsky.feed.post":
        post: Post = record

        # Ignore replies (for now)
        if "reply" in post and post["reply"]:
            continue

        # Ignore embeds (for now)
        if "embed" in post and post["embed"]:
            continue

        batch_obj = {
            "custom_id": post["uri"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": make_prompt(post)},
                ],
                "logprobs": True,
                "temperature": 0.0,
            },
        }

        batch_path = f"{BATCH_DIR}/{BATCH_DESCRIPTION}/in/{i}.jsonl"
        with open(batch_path, "a") as f:
            json.dump(batch_obj, f)
            f.write("\n")

        batch_size += 1
        total_tokens += AVG_TOKENS_PER_REQ

        if batch_size == BATCH_MAX_N or total_tokens > BATCH_QUEUE_MAX_TOKENS:
            print(f"Batch {i} saved: {batch_size} posts, {total_tokens} tokens")
            i += 1
            batch_size = 0
            total_tokens = 0

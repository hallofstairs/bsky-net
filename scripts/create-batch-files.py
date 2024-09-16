import json
import os

from bsky_net import Post, records

# Constants
STREAM_PATH = "data/raw/records-2023-07-01.jsonl"
BATCH_DIR = "data/batches"

BATCH_MAX_N = 50_000
BATCH_QUEUE_MAX_TOKENS = 1_900_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 51
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

SYS_PROMPT = """Classify this Bluesky post as related to the social network's moderation policies (1) or not (0). Focus solely on opinions about how Bluesky handles content moderation."""


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}" """


# Create BatchAPI request
BATCH_DESCRIPTION = "mega-moderation-2023-07-01"
END_DATE = "2023-07-01"

if os.path.exists(f"{BATCH_DIR}/{BATCH_DESCRIPTION}"):
    raise ValueError(f"Batch folder '{BATCH_DESCRIPTION}' already exists.")

os.makedirs(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/in")
os.makedirs(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out")

i = 0
batch_size = 0
total_tokens = 0

# Create a file for each batch of posts
for record in records(stream_path=STREAM_PATH, end_date=END_DATE):
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

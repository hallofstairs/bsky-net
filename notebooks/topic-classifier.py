# %% Imports

import json
import math
import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.batch import Batch

from bsky_net import Post, records

# Load environment variables
load_dotenv()

# Constants
STREAM_DIR = "../data/raw/stream-2023-07-01"
LABELS_DIR = "../data/processed/topic-labels"
BATCH_DIR = "../data/batches"

BATCH_MAX_N = 50_000
BATCH_QUEUE_MAX_TOKENS = 1_900_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 174
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# %% Prompts


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Class:"""


sys_prompt = """You are tasked with analyzing a post from the social network Bluesky to determine if it references the network's moderation policies, especially in relation to the Bluesky development team.

Examples:
Text: "This is definitely the answer. Everyone ranting and raving about moderation decisions here are completely blind to how things will work once federation launches."
Class: 1

Text: "I've seen that Alice chick 4 times now. \n\nJust bury her and block. I thought that was the plan here"
Class: 1

Text: "I think I\u2019ve been on here a month with zero invite codes bluesky mods hate me"
Class: 0

Text: "So wait does "What's Hot Classic" mean the classic feed with nudes or without? Asking for a friend who is in horny jail."
Class: 0"""


# %% Create BatchAPI request

BATCH_DESCRIPTION = "moderation-2023-05-24_2023-05-28"

START_DATE = "2023-05-24"
END_DATE = "2023-05-28"

if os.path.exists(f"{BATCH_DIR}/{BATCH_DESCRIPTION}"):
    raise ValueError(f"Batch folder '{BATCH_DESCRIPTION}' already exists.")

os.makedirs(f"{BATCH_DIR}/{BATCH_DESCRIPTION}")

i = 0
batch_size = 0
total_tokens = 0

# Create batch files based on limits
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
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": make_prompt(post)},
                ],
                "logprobs": True,
                "temperature": 0.0,
            },
        }

        batch_path = f"{BATCH_DIR}/{BATCH_DESCRIPTION}/{i}.jsonl"
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

print(f"Total posts: {batch_size}")
print(f"Total tokens: {total_tokens}")


# %% Push batch files to Batch API

client = OpenAI(api_key=OPENAI_API_KEY)

idx = 0

batch_input_file = client.files.create(
    file=open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/{idx}.jsonl", "rb"),
    purpose="batch",
)

batch = client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={"description": f"{BATCH_DESCRIPTION}-{idx}"},
)


# %% Check on batch

idx = 0

batch_completed = False
batch_id: str | None = None
batch: Batch | None = None


client = OpenAI(api_key=OPENAI_API_KEY)


def push_batch(idx: int):
    batch_input_file = client.files.create(
        file=open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/{idx}.jsonl", "rb"),
        purpose="batch",
    )

    batch = client.batches.create(
        input_file_id=batch_input_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": f"{BATCH_DESCRIPTION}-{idx}"},
    )

    return batch


while True:
    if not batch:
        try:
            batch = push_batch(idx)
        except Exception as e:
            print(e)
            break

    batch_info = client.batches.retrieve(batch.id)

    if batch_info.completed_at:
        if not batch_info.output_file_id:
            raise ValueError("Batch output file ID not found.")

        output = client.files.content(batch_info.output_file_id)

        with open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out/{idx}.jsonl", "w") as f:
            f.write(output.text)

        print(f"Batch {idx} completed and results saved.")
        batch = None
        idx += 1

    time.sleep(60)

# %%

_id = "batch_08fP4pyK3U8JClMRKHgoK6Q1"

batch_info = client.batches.retrieve(_id)

if not batch_info.output_file_id:
    raise ValueError("Batch output file ID not found.")

output = client.files.content(batch_info.output_file_id)

with open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out/2.jsonl", "w") as f:
    f.write(output.text)

# %%

batch_input_file = client.files.create(
    file=open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/{1}.jsonl", "rb"),
    purpose="batch",
)

batch = client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={"description": f"{BATCH_DESCRIPTION}-{1}"},
)

# %% Map results

POSTS_PATH = "../data/raw/posts-2023-07-01.jsonl"
INPUT_PATH = f"{BATCH_DIR}/{BATCH_DESCRIPTION}.jsonl"
OUTPUT_PATH = f"{BATCH_DIR}/batch_Q47CZsPZEutytV7Sw7wAR9lL_output.jsonl"

post_ref: dict[str, str] = {}

for record in records(STREAM_DIR, start_date="2023-05-25", end_date="2023-05-29"):
    if record["$type"] == "app.bsky.feed.post":
        post = Post(**record)

        # Ignore replies (for now)
        if "reply" in post and post["reply"]:
            continue

        # Ignore embeds (for now)
        if "embed" in post and post["embed"]:
            continue

        post_ref[post["uri"]] = post["text"]


count = 0
with open(INPUT_PATH, "r") as inputs, open(OUTPUT_PATH, "r") as outputs:
    for input, output in zip(inputs, outputs):
        input_data: dict = json.loads(input)
        output_data: dict = json.loads(output)

        if input_data["custom_id"] != output_data["custom_id"]:
            raise ValueError(
                f"URI mismatch: {input_data['custom_id']} != {output_data['custom_id']}"
            )

        classification = output_data["response"]["body"]["choices"][0]["message"][
            "content"
        ]
        topic = classification.strip().lower()
        logprobs = output_data["response"]["body"]["choices"][0]["logprobs"]

        probability = (
            math.exp(logprobs["content"][0]["logprob"])
            if logprobs and logprobs["content"]
            else -1
        )

        print(input_data["custom_id"])

        log_entry = {
            "text": post_ref[input_data["custom_id"]],
            "classification": topic,
            "probability": probability,
            "uri": input_data["custom_id"],
        }

        with open(f"{LABELS_DIR}/{BATCH_DESCRIPTION}.jsonl", "a") as log_file:
            json.dump(log_entry, log_file)
            log_file.write("\n")

        count += 1

print(f"Total posts: {count}")

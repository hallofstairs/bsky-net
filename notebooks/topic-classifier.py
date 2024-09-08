# %% Imports

import json
import math
import os

from dotenv import load_dotenv
from openai import OpenAI

from bsky_net import Post, records

# Load environment variables
load_dotenv()

# Constants
STREAM_DIR = "../data/raw/stream-2023-07-01"
LABELS_DIR = "../data/processed/topic-labels"
END_DATE = "2023-05-01"

# %%

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# %% Test simple classifier

TOPICS = ["moderation policy", "unrelated"]


# TODO: Add few-shot examples
def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Topic:"""


zeroshot_prompt = """You are a Bluesky post classifier that identifies any posts talking specifically about *bluesky's* moderation policies. Only respond with the topic, either "moderation policy" or "unrelated"."""

fewshot_prompt = """You are a Bluesky post classifier that identifies any posts talking about Bluesky's moderation policies. Only respond with the topic, nothing else. Here are a few examples:
Text: "This is definitely the answer. Everyone ranting and raving about moderation decisions here are completely blind to how things will work once federation launches."
Topic: moderation policy

Text: "Woah this is really smart. I assumed they would drop the invites, but this makes trust and safety easier."
Topic: moderation policy

Text: "So wait does "What's Hot Classic" mean the classic feed with nudes or without? Asking for a friend who is in horny jail."
Topic: unrelated"""


post_count = 0

for record in records(stream_dir=STREAM_DIR, end_date=END_DATE):
    if record["$type"] == "app.bsky.feed.post":
        # Ignore replies (for now)
        if "reply" in record and record["reply"]:
            continue

        # Ignore embeds (for now)
        if "embed" in record and record["embed"]:
            continue

        post = Post(**record)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": fewshot_prompt,
                },
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
            f"{LABELS_DIR}/moderation-testing-4o-mini-fewshot.jsonl", "a"
        ) as log_file:
            json.dump(log_entry, log_file)
            log_file.write("\n")

        post_count += 1

        if post_count == 1000:
            break

# %% Compare models

total_diffs = 0

with open(f"{LABELS_DIR}/moderation-testing-4o-mini-zeroshot.jsonl", "r") as f1, open(
    f"{LABELS_DIR}/moderation-testing-4o-mini-fewshot.jsonl", "r"
) as f2:
    for model_1, model_2 in zip(f1, f2):
        model_1_data = json.loads(model_1)
        model_2_data = json.loads(model_2)

        # if model_1_data["classification"] != model_2_data["classification"]:
        #     total_diffs += 1
        #     print(
        #         model_1_data["text"],
        #         model_1_data["classification"],
        #         model_1_data["probability"],
        #         model_2_data["classification"],
        #         model_2_data["probability"],
        #     )
        #     print("---")

        if model_1_data["classification"] == "moderation policy":
            print(model_1_data["text"])

    # print(f"Total diffs: {total_diffs}")


# %% BatchAPI request

# ~75 input tokens per post (~0.005625 / 1k posts), ~2 output tokens per post (~0.0006 / 1k posts)
# Total cost: ~0.006225 / 1k posts
# 50k posts: $0.31
# 100k posts: $0.62
# 1m posts: $6.22


BATCH_MAX_N = 50_000
BATCH_QUEUE_MAX_TOKENS = 1_500_000

BATCH_DIR = "../data/batches"
BATCH_DESCRIPTION = "moderation-spike-4o-mini-zeroshot"

AVG_TOKENS_PER_POST = 30.7
INPUT_PROMPT_TOKENS = 40
AVG_TOKENS_PER_REQ = INPUT_PROMPT_TOKENS + AVG_TOKENS_PER_POST

if os.path.exists(f"{BATCH_DIR}/{BATCH_DESCRIPTION}.jsonl"):
    raise ValueError(f"Batch file '{BATCH_DESCRIPTION}.jsonl' already exists.")

batch_size = 0
total_tokens = 0
last_uri = ""

# at://did:plc:j53elsjlcag3iuran5ezcy32/app.bsky.feed.post/3jw7y37h7a427
# at://did:plc:pt5p4naogbcoxqnin32kwuoc/app.bsky.feed.post/3jwj6dxfptc2v
# at://did:plc:yteysv5adlllg4e3xek3e3uk/app.bsky.feed.post/3jwjcpuvhy22r
# Started around here (May 25): at://did:plc:4t2ziwnnescprzorvmrfduey/app.bsky.feed.post/3jwjhkteeq22f

# TODO: Convert all \u2019 and \u2018 to '

# Create BatchAPI jsonl file
for record in records(
    stream_dir=STREAM_DIR, start_date="2023-05-25", end_date="2023-05-29"
):
    if record["$type"] == "app.bsky.feed.post":
        post = Post(**record)

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
                    {"role": "system", "content": zeroshot_prompt},
                    {"role": "user", "content": make_prompt(post)},
                ],
                "logprobs": True,
                "temperature": 0.0,
            },
        }

        with open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}.jsonl", "a") as f:
            json.dump(batch_obj, f)
            f.write("\n")

        batch_size += 1
        total_tokens += AVG_TOKENS_PER_REQ
        last_uri = post["uri"]

        if batch_size == BATCH_MAX_N:
            print(
                f"Batch max posts reached: {batch_size}. Total tokens: {total_tokens}"
            )
            break

        if total_tokens > BATCH_QUEUE_MAX_TOKENS:
            print(
                f"Batch queue max tokens reached: {total_tokens}. Total posts: {batch_size}"
            )
            break

print(f"Total posts: {batch_size}")
print(f"Total tokens: {total_tokens}")
print(
    f"Last URI: {last_uri}"
)  # at://did:plc:2px2wmhufv4jzdolr5fjawmv/app.bsky.feed.post/3jwlp3dllkk2q


# %% Create BatchAPI request

batch_input_file = client.files.create(
    file=open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}.jsonl", "rb"),
    purpose="batch",
)

client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={"description": BATCH_DESCRIPTION},
)

# %% Check on batch

print(client.batches.retrieve("batch_Q47CZsPZEutytV7Sw7wAR9lL"))

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

# %% Looking for start of moderation issue in hellthread

for record in records(
    "../data/raw/stream-2023-07-01", start_date="2023-05-24", end_date="2023-5-25"
):
    if record["$type"] == "app.bsky.feed.post":
        if "@pfrazee.com" in record["text"]:
            print(record["text"])

# %% Prompt testing


# %% Splitting up Batch API requests

BATCH_MAX_N = 50_000
BATCH_QUEUE_MAX_TOKENS = 1_950_000

BATCH_DIR = "../data/batches"
EXPERIMENT_NAME = "moderation-4o-mini-fewshot-v1"

AVG_TOKENS_PER_POST = 30.7
INPUT_PROMPT_TOKENS = 40
AVG_TOKENS_PER_REQ = INPUT_PROMPT_TOKENS + AVG_TOKENS_PER_POST


for record in records(
    "../data/raw/stream-2023-07-01", start_date="2023-05-24", end_date="2023-5-25"
):
    if record["$type"] == "app.bsky.feed.post":
        if "@pfrazee.com" in record["text"]:
            print(record["text"])

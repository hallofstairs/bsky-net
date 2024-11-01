import json
import os

import boto3
from dotenv import load_dotenv

from bsky_net import Post, Prompts, records

load_dotenv()

# Constants
STREAM_PATH = "data/raw/stream-2023-07-01"
LOCAL_DIR = "data/batches"
BUCKET_NAME = "main"
BUCKET_DIR = "bsky-net/batches"
BATCH_DESCRIPTION = "en-moderation-topic-stance-2023-05-28-V2"

START_DATE = "2022-11-17"
END_DATE = "2023-05-28"

MODEL = "gpt-4o-mini"
BATCH_MAX_N = 49_990
BATCH_QUEUE_MAX_TOKENS = 19_000_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 237
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
)


def upload_file(file_path: str):
    """Upload a file to Cloudflare R2"""
    obj_name = os.path.basename(file_path)

    s3.upload_file(file_path, BUCKET_NAME, obj_name)
    print(f"File {file_path} uploaded successfully to {BUCKET_NAME}/{obj_name}")


if os.path.exists(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}"):
    raise ValueError(f"Batch folder '{BATCH_DESCRIPTION}' already exists.")

os.makedirs(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/in")
os.makedirs(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/out")

i = 0
batch_size = 0
total_tokens = 0

# Create a file for each batch of posts
for record in records(
    stream_path=STREAM_PATH, start_date=START_DATE, end_date=END_DATE, log=False
):
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
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": Prompts.TopicStance.SYSTEM},
                    {"role": "user", "content": f"Post: `{post["text"]}`"},
                ],
                "temperature": 0.0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": Prompts.TopicStance.OUTPUT_SCHEMA,
                },
            },
        }

        batch_path = f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/in/{i}.jsonl"
        with open(batch_path, "a") as f:
            json.dump(batch_obj, f)
            f.write("\n")

        batch_size += 1
        total_tokens += AVG_TOKENS_PER_REQ

        if batch_size == BATCH_MAX_N or total_tokens > BATCH_QUEUE_MAX_TOKENS:
            # upload_file(batch_path)
            print(f"Batch {i} saved: {batch_size} posts, {total_tokens} tokens")
            i += 1
            batch_size = 0
            total_tokens = 0


# upload_file(batch_path)
print(f"\nBatch {i} saved: {batch_size} posts, {total_tokens} tokens")

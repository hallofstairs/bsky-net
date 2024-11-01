# Script to filter Bluesky's data stream to be English-only and non-spam.


import json
import os
import shutil
import typing as t

import langid
from pydantic import BaseModel

from bsky_net import Post, Record, TimeFormat, records, truncate_timestamp

STREAM_DIR = "data/raw/stream-2023-07-01"
OUTPUT_DIR = "data/raw/en-stream-2023-07-01"
SPAM_USERS = ["did:plc:czcwobs37px7otals6umpd5j"]


def is_trash(did: str, text: str) -> bool:
    # No text
    if text == "":
        return True

    # Only link
    if (text.startswith("http://") or text.startswith("https://")) and len(
        text.split()
    ) == 1:
        return True

    if did in SPAM_USERS:
        return True

    return False


def is_english(text: str) -> bool:
    return langid.classify(text)[0] == "en"


def is_clean(did: str, text: str) -> bool:
    return not is_trash(did, text) and is_english(text)


class ReplyUris(BaseModel):
    root: str
    parent: str


def get_reply_uris(post: Post) -> ReplyUris:
    if "reply" not in post or not post["reply"]:
        raise ValueError("Post is not a reply")
    return ReplyUris(
        root=post["reply"]["root"]["uri"], parent=post["reply"]["parent"]["uri"]
    )


def get_subject_uri(post: Post) -> t.Optional[str]:
    if "embed" not in post or not post["embed"]:
        raise ValueError("Post is not a quote")

    try:
        if post["embed"]["$type"] == "app.bsky.embed.record":
            return post["embed"]["record"]["uri"]
        elif post["embed"]["$type"] == "app.bsky.embed.recordWithMedia":
            return post["embed"]["record"]["record"]["uri"]
    except KeyError:
        return None


def write_record(record: Record, day: str, output_dir: str):
    with open(f"{output_dir}/{day}.jsonl", "a") as jsonl_file:
        jsonl_file.write(json.dumps(record) + "\n")


# Clear the output directory
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

clean_posts: set[str] = set()  # clean = English, non-spam

# Iterate through records
for record in records(STREAM_DIR):
    did = record["did"]
    day = truncate_timestamp(record["createdAt"], TimeFormat.daily)

    # Process profile creation
    if record["$type"] == "app.bsky.actor.profile":
        write_record(record, day, OUTPUT_DIR)

    # Process follow
    elif record["$type"] == "app.bsky.graph.follow":
        write_record(record, day, OUTPUT_DIR)

    # Process like
    elif record["$type"] == "app.bsky.feed.like":
        # Only save likes to clean posts
        if record["subject"]["uri"] in clean_posts:
            write_record(record, day, OUTPUT_DIR)

    elif record["$type"] == "app.bsky.graph.block":
        write_record(record, day, OUTPUT_DIR)

    # Process repost
    elif record["$type"] == "app.bsky.feed.repost":
        # Only save reposts of clean posts
        if record["subject"]["uri"] in clean_posts:
            write_record(record, day, OUTPUT_DIR)

    # Process post creation
    elif record["$type"] == "app.bsky.feed.post":
        if "reply" in record and record["reply"]:
            reply_uris = get_reply_uris(record)

            # Only save clean replies to clean posts
            if reply_uris.root in clean_posts and is_clean(did, record["text"]):
                write_record(record, day, OUTPUT_DIR)
                continue

        if "embed" in record and record["embed"]:
            subject_uri = get_subject_uri(record)

            # Only save clean quotes of clean posts
            if (
                subject_uri
                and subject_uri in clean_posts
                and is_clean(did, record["text"])
            ):
                write_record(record, day, OUTPUT_DIR)
                continue

        if is_clean(did, record["text"]):
            clean_posts.add(record["uri"])
            write_record(record, day, OUTPUT_DIR)

    else:
        print(f"Not saving record type: {record['$type']}")

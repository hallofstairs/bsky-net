import json
import os
import shutil
import sys

from bsky_net import TimeFormat, records, truncate_timestamp

# Constants
WINDOW_SIZE = TimeFormat[sys.argv[1]]
OUTPUT_PATH = f"data/processed/bsky-net-{WINDOW_SIZE.name}.json"

STREAM_DIR = "data/raw/en-stream-2023-07-01"
OPINIONS_PATH = "data/processed/en-moderation-topic-stance-2023-05-28-V2-zipped.json"

# Load list of post URIs with expressed opinions
with open(OPINIONS_PATH, "r") as f:
    expressed_opinions: dict[str, str] = json.load(f)

# Build graph
bsky_net_graph = {}
follow_graph: dict[str, list[str]] = {}
opinion_post_info: dict[str, dict] = {}

# Iterate through records
for record in records(STREAM_DIR):
    did = record["did"]
    window = truncate_timestamp(record["createdAt"], WINDOW_SIZE)

    if window not in bsky_net_graph:
        if len(opinion_post_info) == len(expressed_opinions):
            print("All labeled posts covered, exiting...")
            break

        bsky_net_graph[window] = {}

    # Process profile creation
    if record["$type"] == "app.bsky.actor.profile":
        follow_graph[did] = []

    # Process follow
    if record["$type"] == "app.bsky.graph.follow":
        subject_did = record["subject"]
        if subject_did not in follow_graph:
            follow_graph[subject_did] = []

        follow_graph[subject_did].append(did)

    # Process like
    if record["$type"] == "app.bsky.feed.like":
        subject_uri = record["subject"]["uri"]

        if subject_uri not in opinion_post_info:
            continue

        post_info = opinion_post_info[subject_uri]

        # Ignore posts not from following (for now)
        if did not in bsky_net_graph[window]:
            continue

        # Ignore posts not from following (for now)
        if subject_uri not in bsky_net_graph[window][did]["seen"]:
            # print(f"Post {subject_uri} not seen by {did} in {window}")
            continue

        bsky_net_graph[window][did]["liked"][subject_uri] = {
            "labels": post_info["labels"],
            "createdAt": record["createdAt"],
        }

    # Process post creation
    if record["$type"] == "app.bsky.feed.post":
        # Ignore replies (for now)
        if "reply" in record and record["reply"]:
            continue

        # Ignore embeds/quotes (for now)
        if "embed" in record and record["embed"]:
            continue

        opinion = expressed_opinions.get(record["uri"], None)

        followers: list[str] = follow_graph.get(record["did"], [])
        post_labels = []

        if opinion:
            post_labels.append(("moderation", opinion))
            opinion_post_info[record["uri"]] = {
                "labels": post_labels,
                "createdAt": record["createdAt"],
            }

        if did not in bsky_net_graph[window]:
            bsky_net_graph[window][did] = {
                "seen": {},
                "posted": {},
                "liked": {},
            }

        bsky_net_graph[window][did]["posted"][record["uri"]] = {
            "text": record["text"],  # For debugging
            "createdAt": record["createdAt"],
            "labels": post_labels,
        }

        for follower_did in followers:
            if follower_did not in bsky_net_graph[window]:
                bsky_net_graph[window][follower_did] = {
                    "seen": {},
                    "posted": {},
                    "liked": {},
                }

            bsky_net_graph[window][follower_did]["seen"][record["uri"]] = {
                "labels": post_labels,
                "createdAt": record["createdAt"],
            }

OUTPUT_DIR = f"data/processed/bsky-net-{WINDOW_SIZE.name}"

# Clear the output directory
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

for step, data in bsky_net_graph.items():
    with open(f"{OUTPUT_DIR}/{step}.json", "w") as json_file:
        json.dump(data, json_file, indent=4)

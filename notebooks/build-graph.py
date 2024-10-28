# %% Imports

import json
from datetime import datetime
from enum import Enum

from bsky_net import records

# Constants
STREAM_DIR = "../data/raw/stream-2023-07-01"
EXPRESSED_OPINION_URIS_FILE = (
    "../data/processed/expressed-opinion-uris-2023-05-24_2023-05-28.txt"
)

# Helpers


class TimeFormat(str, Enum):
    minute = "%Y-%m-%dT%H:%M"
    hourly = "%Y-%m-%dT%H"
    daily = "%Y-%m-%d"
    weekly = "%Y-%W"
    monthly = "%Y-%m"


def get_time_window(created_at: str, format: TimeFormat) -> str:
    """
    Get the relevant subset of a timestamp for a given grouping.

    e.g. "2023-01-01" for "daily, "2023-01" for "monthly"
    """
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime(format)


# %% Load expressed opinion URIs

expressed_opinions: dict[str, str] = {}

with open(EXPRESSED_OPINION_URIS_FILE, "r") as f:
    for line in f:
        uri, opinion = line.strip().split(",")
        expressed_opinions[uri] = opinion


# %% Build graph

WINDOW_SIZE = TimeFormat.daily

bsky_net_graph = {}
follow_graph: dict[str, list[str]] = {}
on_topic_post_ref: dict[str, dict] = {}

# Iterate through records
for record in records(STREAM_DIR, end_date="2023-05-28"):
    did = record["did"]
    window = get_time_window(record["createdAt"], WINDOW_SIZE)

    if window not in bsky_net_graph:
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

        if subject_uri not in on_topic_post_ref:
            continue

        post_info = on_topic_post_ref[subject_uri]

        # Ignore posts not from following (for now)
        if did not in bsky_net_graph[window]:
            continue

        # Ignore posts not from following (for now)
        if subject_uri not in bsky_net_graph[window][did]["seen"]:
            # print(f"Post {subject_uri} not seen by {did} in {window}")
            continue

        bsky_net_graph[window][did]["liked"][subject_uri] = {
            "opinion": post_info["opinion"],
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

        # Ignore off-topic posts (for now)
        if not opinion:
            continue

        followers: list[str] = follow_graph.get(record["did"], [])
        on_topic_post_ref[record["uri"]] = {
            "opinion": opinion,
            "createdAt": record["createdAt"],
        }

        for follower_did in followers:
            if follower_did not in bsky_net_graph[window]:
                bsky_net_graph[window][follower_did] = {"seen": {}, "liked": {}}

            bsky_net_graph[window][follower_did]["seen"][record["uri"]] = {
                "opinion": opinion,
                "createdAt": record["createdAt"],
            }

# Write to file
with open("../data/processed/bsky-net-test-2.json", "w") as json_file:
    json.dump(bsky_net_graph, json_file, indent=4)

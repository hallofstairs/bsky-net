# %% Imports

import json
import random
import typing as t
from datetime import datetime, timedelta

from bsky_net.utils import did_from_uri, tq

# %% Helpers

# Constants
STREAM_DIR = "../data/raw/chron-stream-2023-07-01"
END_DATE = "2023-01-01"
TOPIC = "moderation"


def generate_timestamps(start_date: str, end_date: str) -> list[str]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    delta = end_dt - start_dt

    return [
        (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(delta.days + 1)
    ]


def records(
    start_date: str = "2022-11-17", end_date: str = "2023-05-01"
) -> t.Generator[dict, None, None]:
    """
    Generator that yields records from the stream for the given date range.

    start_date, end_date (inclusive)
    """
    for ts in tq(generate_timestamps(start_date, end_date)):
        for line in open(f"{STREAM_DIR}/{ts}.jsonl", "r"):
            try:
                yield json.loads(line.strip())
            except json.JSONDecodeError:
                continue


# TODO: Placeholder -- returns random label
def is_topical(text: str, topic: str) -> bool:
    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    return True if random.random() < 0.01 else False


# TODO: Placeholder -- returns random label
def classify_post_opinion(text: str) -> int:
    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    return random.choice([-1, 0, 1])


class Post(t.TypedDict):
    did: str
    uri: str
    text: str
    createdAt: str
    reply: t.Optional[dict]
    embed: t.Optional[dict]


class AnnotatedPost(Post):
    topical: bool
    opinion: int


class ReplyReaction(t.TypedDict):
    type: t.Literal["reply"]
    did: str
    createdAt: str
    expressed_opinion: int


class QuoteReaction(ReplyReaction):
    pass


class LikeReaction(t.TypedDict):
    type: t.Literal["like"]
    did: str
    createdAt: str


class RepostReaction(t.TypedDict):
    type: t.Literal["repost"]
    did: str
    createdAt: str


class Follow(t.TypedDict):
    did: str
    createdAt: str


class Node(t.TypedDict):
    createdAt: str
    followers: list[Follow]


class StatusUpdate(t.TypedDict):
    did: str
    createdAt: str
    expressed_opinion: int
    consumers: dict[str, "Consumer"]


class Consumer(t.TypedDict):
    type: t.Literal["follower", "non-follower"]
    reactions: list[ReplyReaction | QuoteReaction | LikeReaction | RepostReaction]


# %% Reconstruct network interactions


status_updates: dict[str, StatusUpdate] = {}
graph: dict[str, Node] = {}

seen_non_follows = 0

# TODO: Ignore interactions with self

for record in records(end_date=END_DATE):
    if record["$type"] == "app.bsky.actor.profile":
        graph[record["did"]] = {"createdAt": record["createdAt"], "followers": []}

    if record["$type"] == "app.bsky.feed.post":
        post = Post(**record)

        # Don't consider replies as status updates
        if "reply" in post and post["reply"]:
            reply = post["reply"]
            root_uri = reply["root"]["uri"]
            root_did = did_from_uri(root_uri)

            # Ignore replies to self
            if post["did"] == root_did:
                continue

            # Ignore replies to non-topical posts
            if root_uri not in status_updates:
                continue

            # TODO: Only considering direct replies to parent rn
            if root_uri != reply["parent"]["uri"]:
                continue

            opinion_of_reply: int = classify_post_opinion(post["text"])
            reaction = ReplyReaction(
                {
                    "type": "reply",
                    "did": post["did"],
                    "createdAt": post["createdAt"],
                    "expressed_opinion": opinion_of_reply,
                }
            )

            # Non-follower replied to post
            if post["did"] not in status_updates[root_uri]["consumers"]:
                seen_non_follows += 1  # Just for logging
                status_updates[root_uri]["consumers"][post["did"]] = {
                    "type": "non-follower",
                    "reactions": [],
                }

            status_updates[root_uri]["consumers"][post["did"]]["reactions"].append(
                reaction
            )

        # Handle posts with embeds
        if (
            "embed" in post and post["embed"]
            # and (
            #     post["embed"]["$type"] == "app.bsky.embed.record"
            #     or post["embed"]["$type"] == "app.bsky.embed.recordWithMedia"
            # )
        ):
            # TODO: Handle posts with embeds
            continue

        if is_topical(post["text"], TOPIC):
            if post["did"] not in graph:
                graph[post["did"]] = {"createdAt": post["createdAt"], "followers": []}

            opinion: int = classify_post_opinion(post["text"])
            consumers: dict[str, Consumer] = {
                node["did"]: {"type": "follower", "reactions": []}
                for node in graph[post["did"]]["followers"]
            }

            status_updates[post["uri"]] = {
                "did": post["did"],
                "createdAt": post["createdAt"],
                "expressed_opinion": opinion,
                "consumers": consumers,
            }

    if record["$type"] == "app.bsky.graph.follow":
        if record["subject"] not in graph:
            graph[record["subject"]] = {
                "createdAt": record["createdAt"],
                "followers": [],
            }

        graph[record["subject"]]["followers"].append(
            {"did": record["did"], "createdAt": record["createdAt"]}
        )

    if record["$type"] == "app.bsky.feed.like":
        post_uri = record["subject"]["uri"]
        post_did = did_from_uri(post_uri)

        # Ignore likes for self
        if record["did"] == post_did:
            continue

        # Ignore likes of non-topical posts
        if post_uri not in status_updates:
            continue

        reaction = LikeReaction(
            {"type": "like", "did": record["did"], "createdAt": record["createdAt"]}
        )

        # Non-follower liked post
        if record["did"] not in status_updates[post_uri]["consumers"]:
            seen_non_follows += 1  # Just for logging
            status_updates[post_uri]["consumers"][record["did"]] = {
                "type": "non-follower",
                "reactions": [],
            }

        status_updates[post_uri]["consumers"][record["did"]]["reactions"].append(
            reaction
        )

    if record["$type"] == "app.bsky.feed.repost":
        post_uri = record["subject"]["uri"]
        post_did = did_from_uri(post_uri)

        # Ignore reposts of self
        if record["did"] == post_did:
            continue

        # Ignore reposts of non-topical posts
        if post_uri not in status_updates:
            continue

        reaction = RepostReaction(
            {"type": "repost", "did": record["did"], "createdAt": record["createdAt"]}
        )

        # Non-follower reposted post
        if record["did"] not in status_updates[post_uri]["consumers"]:
            seen_non_follows += 1  # Just for logging
            status_updates[post_uri]["consumers"][record["did"]] = {
                "type": "non-follower",
                "reactions": [],
            }

        status_updates[post_uri]["consumers"][record["did"]]["reactions"].append(
            reaction
        )


with open(f"../data/processed/status-updates-{END_DATE}.json", "w") as f:
    json.dump(status_updates, f, indent=2)

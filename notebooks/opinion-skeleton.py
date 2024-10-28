# %% Imports

import json
import random
import typing as t
from datetime import datetime
from enum import Enum

from bsky_net import Post, did_from_uri, records

# Constants
STREAM_DIR = "../data/raw/chron-stream-2023-07-01"
END_DATE = "2022-11-17"
TOPIC = "moderation"


# TODO: Placeholder -- returns random label
def is_topical(text: str, topic: str) -> bool:
    """Determine if a post is relevant to the topic being examined."""

    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    # return True if random.random() < 0.01 else False
    return True  # TODO: Remove


# TODO: Placeholder -- returns random label
def classify_post_opinion(text: str) -> int:
    """Classify the opinion expressed in a post towards the topic being examined."""

    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    return random.choice([-1, 0, 1])


# %% Generate validation set


class Impression(t.TypedDict):
    did: str
    uri: str
    createdAt: str
    in_network: bool
    expressed_opinion: int
    reactions: list[dict]


class UserTimestep(t.TypedDict):
    interactive: bool
    consumed: dict[str, Impression]


class TimeFormat(str, Enum):
    hourly = "%Y-%m-%d-%H"
    daily = "%Y-%m-%d"
    weekly = "%Y-%W"
    monthly = "%Y-%m"


graph: dict[str, dict] = {}
impressions: dict[str, dict[str, UserTimestep]] = {}
post_ref: dict[str, dict] = {}  # Store of all relevant posts
time_period: t.Literal["%Y-%m-%d-%H", "%Y-%m-%d", "%Y-%W", "%Y-%m"] = (
    TimeFormat.daily.value
)


# TODO: Use OOP?
# Currently, only considering reactions to posts that occur within the same time period


def get_time_key(created_at: str, grouping: str) -> str:
    """
    Get the relevant subset of a timestamp for a given grouping.

    e.g. "2023-01-01" for "daily, "2023-01" for "monthly"
    """
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime(grouping)


def add_reaction(
    type: t.Literal["reply", "quote", "like", "repost"],
    time_key: str,
    did: str,
    post_uri: str,
    created_at: str,
    opinion: t.Optional[int] = None,
):
    post_did = did_from_uri(post_uri)

    if not post_did:
        return

    # Post is missing from the user's consumption dict
    if post_uri not in impressions[time_key][did]["consumed"]:
        # Missing bc it's not topical -- ignore
        if post_uri not in post_ref:
            return

        post_info = post_ref[post_uri]

        # Missing bc it was created outside of the current timestep -- ignore
        if time_key != get_time_key(post_info["createdAt"], time_period):
            return

        impression: Impression = {
            "did": post_did,
            "uri": post_uri,
            "in_network": False,
            "createdAt": post_info["createdAt"],
            "expressed_opinion": post_info["expressed_opinion"],
            "reactions": [],
        }

        # Missing bc the user didn't follow the author -- add to "consumed"
        impressions[time_key][did]["consumed"][post_uri] = impression

    # Add reaction to consumer's reaction dict for that post
    if opinion:
        reaction = {"type": type, "createdAt": created_at, "expressed_opinion": opinion}
    else:
        reaction = {"type": type, "createdAt": created_at}

    impressions[time_key][did]["consumed"][post_uri]["reactions"].append(reaction)


# TODO: CHECK IF THIS WORKS CORRECTLY
# TODO: IT"S NOT WORKING CORRECTLY
for record in records("../data/raw/bluesky", end_date=END_DATE):
    time_key = get_time_key(record["createdAt"], time_period)

    # Initialize time period, if needed
    if time_key not in impressions:
        impressions[time_key] = {}

    # Mark user who created the record as "interactive" for this time period
    if record["did"] not in impressions[time_key]:
        impressions[time_key][record["did"]] = {"interactive": False, "consumed": {}}
    impressions[time_key][record["did"]]["interactive"] = True

    # Process profile creation
    if record["$type"] == "app.bsky.actor.profile":
        graph[record["did"]] = {"createdAt": record["createdAt"], "followers": []}

    # Process post creation
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
            if root_uri not in post_ref:
                continue

            # TODO: Only considering direct replies to parent rn
            if root_uri != reply["parent"]["uri"]:
                continue

            opinion_of_reply: int = classify_post_opinion(post["text"])
            add_reaction(
                "reply",
                time_key,
                post["did"],
                root_uri,
                post["createdAt"],
                opinion_of_reply,
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

        # Only consider posts related to the topic being examined
        if is_topical(post["text"], TOPIC):
            # Initialize user, if needed
            if post["did"] not in graph:
                graph[post["did"]] = {
                    "createdAt": post["createdAt"],
                    "followers": [],
                }

            # Classify the opinion expressed in the post
            opinion: int = classify_post_opinion(post["text"])

            # Add post to store of relevant posts
            post_ref[post["uri"]] = {
                "did": post["did"],
                "createdAt": post["createdAt"],
                "expressed_opinion": opinion,
            }

            # Fan out post to followers' consumption dicts
            for node in graph[post["did"]]["followers"]:
                # Initialize follower's consumption dict for timestep, if needed
                if node["did"] not in impressions[time_key]:
                    impressions[time_key][node["did"]] = {
                        "interactive": False,
                        "consumed": {},
                    }

                # Add post to follower's "consumed" dict for timestep
                impressions[time_key][node["did"]]["consumed"][post["uri"]] = {
                    "did": post["did"],
                    "uri": post["uri"],
                    "in_network": True,
                    "createdAt": post["createdAt"],
                    "expressed_opinion": opinion,
                    "reactions": [],
                }

    # Process like
    if record["$type"] == "app.bsky.feed.like":
        add_reaction(
            "like",
            time_key,
            record["did"],
            record["subject"]["uri"],
            record["createdAt"],
        )

    # Process repost
    if record["$type"] == "app.bsky.feed.repost":
        add_reaction(
            "repost",
            time_key,
            record["did"],
            record["subject"]["uri"],
            record["createdAt"],
        )

    # Process follow
    if record["$type"] == "app.bsky.graph.follow":
        if record["subject"] not in graph:
            graph[record["subject"]] = {
                "createdAt": record["createdAt"],
                "followers": [],
            }

        graph[record["subject"]]["followers"].append(
            {"did": record["did"], "createdAt": record["createdAt"]}
        )

with open(f"../data/processed/impressions-{END_DATE}.json", "w") as f:
    json.dump(impressions, f, indent=2)

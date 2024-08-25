"""Process raw data stream into a temporal graph that can be used for opinion simulation."""

import json
import os
import random
import typing as t
from datetime import datetime
from enum import Enum

from bsky_net import did_from_uri, records


class TimeFormat(Enum):
    hourly = "%Y-%m-%d-%H"
    daily = "%Y-%m-%d"
    weekly = "%Y-%W"
    monthly = "%Y-%m"


# ===== Helper functions =====


def get_time_key(created_at: str, grouping: str) -> str:
    """
    Get the relevant subset of a timestamp for a given grouping.
    e.g. "2023-01-01" for "daily, "2023-01" for "monthly"
    """
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime(grouping)


def extract_quoted_uri(post: "Post") -> t.Optional[str]:
    if "embed" not in post or not post["embed"]:
        return None

    try:
        if post["embed"]["$type"] == "app.bsky.embed.record":
            return post["embed"]["record"]["uri"]
        elif post["embed"]["$type"] == "app.bsky.embed.recordWithMedia":
            return post["embed"]["record"]["record"]["uri"]
    except KeyError:
        return None


# TODO: Placeholder -- returns random label
def is_on_topic(text: str) -> bool:
    """Determine if a post is related to the topic being considered."""

    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    # return True if random.random() < 0.01 else False
    return True  # TODO: Remove


# TODO: Placeholder -- returns random label
def classify_post_opinion(text: str) -> int:
    """Classify the opinion expressed in a post towards the topic being considered."""

    # TODO: Include analysis of embeds? Images, quoted post, links, etc.
    return random.choice([-1, 0, 1])


# ===== Type hints =====


class Post(t.TypedDict):
    did: str
    uri: str
    text: str
    createdAt: str
    reply: t.Optional[dict[str, dict]]
    embed: t.Optional[dict[str, t.Any]]


class Follow(t.TypedDict):
    did: str  # DID of the follower
    createdAt: str  # Timestamp of the follow


class Node(t.TypedDict):
    createdAt: str  # Timestamp of the user's profile creation
    followers: list[Follow]  # List of followers


class Impression(t.TypedDict):
    did: str  # DID of the user observing the post
    uri: str  # URI of the post
    createdAt: str  # Timestamp of the observation
    in_network: bool  # Whether the user follows the author of the post
    expressed_opinion: int  # Opinion expressed in the post
    reactions: list[dict]  # List of this user's reactions to the post


class UserTimestep(t.TypedDict):
    interactive: bool  # Whether user was interactive on Bluesky during time period
    consumed: dict[str, Impression]  # All observations for this user during time period


# ===== Main script =====

STREAM_DIR = "./data/raw/stream-2023-07-01"
OUTPUT_DIR = "./data/processed"
END_DATE = "2023-04-01"  # TODO: Extend this

if __name__ == "__main__":
    # Graph of users and their followers
    follow_graph: dict[str, Node] = {}

    # Temporal graph of user observations and interactions
    engagement_graph: dict[str, dict[str, UserTimestep]] = {}

    # Store of all on-topic posts
    post_ref: dict[str, dict] = {}

    # Time period for which to group data
    time_period = TimeFormat.daily

    record_count = 0

    def add_interaction(
        type: t.Literal["reply", "quote", "like", "repost"],
        time_key: str,
        did: str,
        post_uri: str,
        created_at: str,
        opinion: t.Optional[int] = None,
    ) -> None:
        """Add a user's interaction with a post for a given time step in the graph."""

        post_did = did_from_uri(post_uri)

        # Misformatted URI
        if not post_did:
            return

        # Post is missing from the user's consumption dict
        if post_uri not in engagement_graph[time_key][did]["consumed"]:
            # Missing bc it's not topical -- ignore
            if post_uri not in post_ref:
                return

            post_info = post_ref[post_uri]

            # Missing bc it was created outside of the current timestep -- ignore
            if time_key != get_time_key(post_info["createdAt"], time_period.value):
                return

            # Missing bc the user didn't follow the author -- add to "consumed"
            engagement_graph[time_key][did]["consumed"][post_uri] = {
                "did": post_did,
                "uri": post_uri,
                "in_network": False,
                "createdAt": post_info["createdAt"],
                "expressed_opinion": post_info["expressed_opinion"],
                "reactions": [],
            }

        # Add reaction to consumer's reaction dict for that post
        if opinion:
            reaction = {
                "type": type,
                "createdAt": created_at,
                "expressed_opinion": opinion,
            }
        else:
            reaction = {"type": type, "createdAt": created_at}

        engagement_graph[time_key][did]["consumed"][post_uri]["reactions"].append(
            reaction
        )

        return

    for record in records(stream_dir=STREAM_DIR, end_date=END_DATE):
        time_key = get_time_key(record["createdAt"], time_period.value)
        record_count += 1

        # Initialize time period, if needed
        if time_key not in engagement_graph:
            engagement_graph[time_key] = {}

        # Mark user who created the record as "interactive" for this time period
        if record["did"] not in engagement_graph[time_key]:
            engagement_graph[time_key][record["did"]] = {
                "interactive": False,
                "consumed": {},
            }
        engagement_graph[time_key][record["did"]]["interactive"] = True

        # Process profile creation
        if record["$type"] == "app.bsky.actor.profile":
            follow_graph[record["did"]] = {
                "createdAt": record["createdAt"],
                "followers": [],
            }

        # Process post creation
        if record["$type"] == "app.bsky.feed.post":
            post = Post(**record)

            # Don't consider replies as status updates
            if "reply" in post and post["reply"]:
                reply = post["reply"]
                root_uri = reply["root"]["uri"]
                root_did = did_from_uri(root_uri)

                # Misformatted URI
                if not root_did:
                    continue

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
                add_interaction(
                    "reply",
                    time_key,
                    post["did"],
                    root_uri,
                    post["createdAt"],
                    opinion_of_reply,
                )

            # Handle posts with embeds
            if "embed" in post and post["embed"]:
                subject_uri = extract_quoted_uri(post)

                # Not a quote post
                if not subject_uri:
                    continue

                subject_did = did_from_uri(subject_uri)

                # Misformatted URI
                if not subject_did:
                    continue

                # Ignore quote posts to self
                if post["did"] == subject_did:
                    continue

                # Ignore quotes to non-topical posts
                if subject_uri not in post_ref:
                    continue

                opinion_of_reply: int = classify_post_opinion(post["text"])
                add_interaction(
                    "quote",
                    time_key,
                    post["did"],
                    subject_uri,
                    post["createdAt"],
                    opinion_of_reply,
                )

            # Only consider on-topic posts
            if is_on_topic(post["text"]):
                # Initialize user, if needed
                if post["did"] not in follow_graph:
                    follow_graph[post["did"]] = {
                        "createdAt": post["createdAt"],
                        "followers": [],
                    }

                # Classify the opinion expressed in the post
                opinion: int = classify_post_opinion(post["text"])

                # Add post to store of on-topic posts
                post_ref[post["uri"]] = {
                    "did": post["did"],
                    "createdAt": post["createdAt"],
                    "expressed_opinion": opinion,
                }

                # Fan out post to followers' consumption dicts
                for node in follow_graph[post["did"]]["followers"]:
                    # Initialize follower's consumption dict for timestep, if needed
                    if node["did"] not in engagement_graph[time_key]:
                        engagement_graph[time_key][node["did"]] = {
                            "interactive": False,
                            "consumed": {},
                        }

                    # Add post to follower's "consumed" dict for timestep
                    engagement_graph[time_key][node["did"]]["consumed"][post["uri"]] = {
                        "did": post["did"],
                        "uri": post["uri"],
                        "in_network": True,
                        "createdAt": post["createdAt"],
                        "expressed_opinion": opinion,
                        "reactions": [],
                    }

        # Process like
        if record["$type"] == "app.bsky.feed.like":
            add_interaction(
                "like",
                time_key,
                record["did"],
                record["subject"]["uri"],
                record["createdAt"],
            )

        # Process repost
        if record["$type"] == "app.bsky.feed.repost":
            add_interaction(
                "repost",
                time_key,
                record["did"],
                record["subject"]["uri"],
                record["createdAt"],
            )

        # Process follow
        if record["$type"] == "app.bsky.graph.follow":
            if record["subject"] not in follow_graph:
                follow_graph[record["subject"]] = {
                    "createdAt": record["createdAt"],
                    "followers": [],
                }

            follow_graph[record["subject"]]["followers"].append(
                {"did": record["did"], "createdAt": record["createdAt"]}
            )

    # Save data
    graph_dir = f"{OUTPUT_DIR}/engagement-{time_period.name}-{END_DATE}"
    os.makedirs(graph_dir, exist_ok=True)

    for time_key, data in engagement_graph.items():
        with open(f"{graph_dir}/{time_key}.json", "w") as f:
            json.dump(data, f, indent=2)

    print(f"Processed {record_count} records across {len(engagement_graph)} timesteps.")
    print(f"Temporal engagement graph saved to {graph_dir}/")

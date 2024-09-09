import json
import typing as t
from datetime import datetime, timedelta

from bsky_net.utils import tq


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


def generate_timestamps(start_date: str, end_date: str) -> list[str]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    delta = end_dt - start_dt

    return [
        (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(delta.days + 1)
    ]


def records(
    stream_dir: str,
    start_date: str = "2022-11-17",
    end_date: str = "2023-05-01",
    log: bool = False,
) -> t.Generator[dict[str, t.Any], None, None]:
    """
    Generator that yields records from the stream for the given date range.

    End date is inclusive.
    """
    for ts in tq(generate_timestamps(start_date, end_date), active=log):
        with open(f"{stream_dir}/{ts}.jsonl", "r") as file:
            for line in file:
                try:
                    yield json.loads(line.strip())
                except json.JSONDecodeError:
                    continue


def did_from_uri(uri: str) -> t.Optional[str]:
    if not uri:
        print("\nMisformatted URI (empty string)")
        return None

    try:
        return uri.split("/")[2]
    except Exception:
        print("\nMisformatted URI: ", uri)
        return None

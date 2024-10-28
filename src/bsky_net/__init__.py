import json
import sys
import time
import typing as t
from datetime import datetime, timedelta

from openai.types.shared_params.response_format_json_schema import JSONSchema

T = t.TypeVar("T")


# === Iteration utils ===


class jsonl[T]:
    @classmethod
    def iter(cls, path: str) -> t.Generator[T, None, None]:
        with open(path, "r") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"JSONDecodeError: {line}")
                    continue


def records(
    stream_path: str = "../data/raw/stream-2023-07-01",
    start_date: str = "2022-11-17",
    end_date: str = "2023-05-01",
    log: bool = True,
) -> t.Generator["Record", None, None]:
    """
    Generator that yields records from the stream for the given date range.

    End date is inclusive.
    """

    def generate_timestamps(start_date: str, end_date: str) -> list[str]:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        delta = end_dt - start_dt

        return [
            (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(delta.days + 1)
        ]

    for ts in tq(generate_timestamps(start_date, end_date), active=log):
        for record in jsonl[Record].iter(f"{stream_path}/{ts}.jsonl"):
            yield record


def tq(iterable: t.Iterable[T], active: bool = True) -> t.Generator[T, None, None]:
    total = len(iterable) if isinstance(iterable, t.Sized) else None

    start_time = time.time()
    estimated_time_remaining = 0

    for i, item in enumerate(iterable):
        if active:
            if total:
                elapsed_time = time.time() - start_time
                items_per_second = (i + 1) / elapsed_time if elapsed_time > 0 else 0
                estimated_time_remaining = (
                    (total - i - 1) / items_per_second if items_per_second > 0 else 0
                )
                sys.stdout.write(
                    f"\r{i+1}/{total} ({((i+1)/total)*100:.2f}%) - {estimated_time_remaining/60:.1f}m until done"
                )
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\rProcessed: {i+1}")
                sys.stdout.flush()

        yield item


# === Data types ===


class CidUri(t.TypedDict):
    cid: str
    uri: str


Post = t.TypedDict(
    "Post",
    {
        "$type": t.Literal["app.bsky.feed.post"],
        "did": str,
        "uri": str,
        "text": str,
        "createdAt": str,
        "reply": t.Optional[dict[t.Literal["root", "parent"], CidUri]],
        "embed": t.Optional[dict[str, t.Any]],
    },
)

Follow = t.TypedDict(
    "Follow",
    {
        "$type": t.Literal["app.bsky.graph.follow"],
        "did": str,  # DID of the follower
        "uri": str,  # URI of the follow record
        "createdAt": str,  # Timestamp of the follow
        "subject": str,  # DID of the followed user
    },
)

Repost = t.TypedDict(
    "Repost",
    {
        "$type": t.Literal["app.bsky.feed.repost"],
        "did": str,
        "uri": str,
        "createdAt": str,
        "subject": CidUri,
    },
)

Like = t.TypedDict(
    "Like",
    {
        "$type": t.Literal["app.bsky.feed.like"],
        "did": str,
        "uri": str,
        "createdAt": str,
        "subject": CidUri,
    },
)

Block = t.TypedDict(
    "Block",
    {
        "$type": t.Literal["app.bsky.graph.block"],
        "did": str,
        "uri": str,
        "createdAt": str,
        "subject": str,
    },
)

Profile = t.TypedDict(
    "Profile",
    {
        "$type": t.Literal["app.bsky.actor.profile"],
        "did": str,
        "createdAt": str,
    },
)

Record = Post | Follow | Repost | Like | Block | Profile


# === Data utils ===


def did_from_uri(uri: str) -> str:
    if not uri:
        raise ValueError("\nMisformatted URI (empty string)")

    try:
        return uri.split("/")[2]
    except Exception:
        raise ValueError(f"\nMisformatted URI: {uri}")


# === Prompts ===


class Prompts:
    class Topic:
        SYSTEM: str = """You are an NLP expert, tasked with performing opinion mining on posts from the Bluesky social network. Your goal is to detect the post author's opinion on the Bluesky team's approach thus far to moderation and trust and safety (T&S) on their platform. 

If the post is unrelated to moderation on Bluesky, indicate that the post is 'off-topic'.

Include quotes from the text that you used to reach your answer."""

        OUTPUT_SCHEMA: JSONSchema = {
            "name": "opinion_mining",
            "strict": True,
            "schema": {
                "type": "object",
                "required": ["reasoning", "on_topic"],
                "additionalProperties": False,
                "properties": {
                    "reasoning": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["quote", "conclusion"],
                            "properties": {
                                "quote": {"type": "string"},
                                "conclusion": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "on_topic": {"type": "boolean"},
                },
            },
        }

    class Stance:
        SYSTEM: str = """You are an NLP expert, tasked with performing stance detection on posts from the Bluesky social network. Your goal is to detect the post author's stance on the Bluesky team's approach to moderation and trust and safety (T&S) on their platform.

If the post is unrelated to social media moderation on Bluesky specifically, indicate that the post is 'off-topic'.

If the post is on-topic, classify the stance of the author on the BLUESKY TEAM's MODERATION EFFORTS as defending/sympathizing with them (favor), criticizing them (against), or neither (none). If the post's opinion is not directed towards the BLUESKY TEAM's moderation approach, even if it's on-topic, indicate that the opinion is 'none'.

Include quotes from the text that you used to reach your answer."""

        OUTPUT_SCHEMA: JSONSchema = {
            "name": "stance_detection",
            "strict": True,
            "schema": {
                "type": "object",
                "required": ["reasoning", "on_topic", "opinion"],
                "additionalProperties": False,
                "properties": {
                    "reasoning": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["quote", "conclusion"],
                            "properties": {
                                "quote": {"type": "string"},
                                "conclusion": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "on_topic": {"type": "boolean"},
                    "opinion": {"enum": ["favor", "against", "none"], "type": "string"},
                },
            },
        }

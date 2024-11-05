import mmap
import os
import sys
import time
import typing as t
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import ujson as json
from openai.types.shared_params.response_format_json_schema import JSONSchema

T = t.TypeVar("T")

ExpressedBelief = t.Literal["favor", "against", "none"]
InternalBelief = t.Literal["favor", "against"]
Label = tuple[str, ExpressedBelief]


class LabeledReaction(t.TypedDict):
    labels: list[Label]
    createdAt: str


class LabeledPost(t.TypedDict):
    labels: list[Label]
    createdAt: str


LabeledRecord = LabeledReaction | LabeledPost


class UserActivity(t.TypedDict):
    seen: dict[str, LabeledRecord]
    posted: dict[str, LabeledRecord]
    liked: dict[str, LabeledRecord]


class BskyNet:
    def __init__(self, path: str) -> None:
        self.path = path

        self.files = self._get_files()
        self.time_steps = self._get_time_steps()

    def simulate(
        self, verbose: bool = True
    ) -> t.Generator[tuple[int, dict[str, UserActivity]], None, None]:
        for i, time_step in enumerate(tq(self.files, active=verbose)):
            with open(f"{self.path}/{time_step}", "r") as json_file:
                yield i, json.load(json_file)

    def _get_files(self):
        return [f for f in sorted(os.listdir(self.path)) if f.endswith(".json")]

    def _get_time_steps(self) -> list[str]:
        return [Path(f).stem for f in self.files]

    def get_beliefs(
        self, topic: str, records: dict[str, LabeledRecord]
    ) -> list[ExpressedBelief]:
        return [
            rec_opinion
            for rec in records.values()
            for rec_topic, rec_opinion in rec["labels"]
            if rec_topic == topic
        ]


# === Iteration utils ===


class jsonl[T]:
    @classmethod
    def iter(cls, path: str) -> t.Generator[T, None, None]:
        with open(path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                for line in iter(mm.readline, b""):
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        print(f"JSONDecodeError: {line}")
                        continue


def records(
    stream_path: str = "../data/raw/en-stream-2023-07-01",
    start_date: str = "2022-11-17",
    end_date: str = "2023-07-01",
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


class TimeFormat(str, Enum):
    minute = "%Y-%m-%dT%H:%M"
    hourly = "%Y-%m-%dT%H"
    daily = "%Y-%m-%d"
    weekly = "%Y-%W"
    monthly = "%Y-%m"


def truncate_timestamp(timestamp: str, format: TimeFormat) -> str:
    """
    Get the relevant subset of a timestamp for a given grouping.

    e.g. "2023-01-01" for "daily, "2023-01" for "monthly"
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime(format)


def did_from_uri(uri: str) -> str:
    if not uri:
        raise ValueError("\nMisformatted URI (empty string)")

    try:
        return uri.split("/")[2]
    except Exception:
        raise ValueError(f"\nMisformatted URI: {uri}")


def rkey_from_uri(uri: str) -> str:
    return uri.split("/")[-1]


class s32:
    S32_CHAR = "234567abcdefghijklmnopqrstuvwxyz"

    @classmethod
    def encode(cls, i: int) -> str:
        s = ""
        while i:
            c = i % 32
            i = i // 32
            s = s32.S32_CHAR[c] + s
        return s

    @classmethod
    def decode(cls, s: str) -> int:
        i = 0
        for c in s:
            i = i * 32 + s32.S32_CHAR.index(c)
        return i


def parse_rkey(rev: str) -> tuple[datetime, int]:
    """Extract the data from the rkey of a URI"""

    timestamp = s32.decode(rev[:-2])  # unix, microseconds
    clock_id = s32.decode(rev[-2:])

    timestamp = datetime.fromtimestamp(timestamp / 1_000_000)
    return timestamp, clock_id


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

    class TopicStance:
        SYSTEM: str = """You are an NLP expert, tasked with performing opinion mining on posts from the Bluesky social network. Your goal is to detect the post author's opinion on the Bluesky team's approach thus far to moderation and trust and safety (T&S) on their platform. 

If the post is unrelated to moderation on Bluesky, indicate that the post is 'off-topic'.

If the post is on-topic, classify if the post is defending/sympathizing with THE BLUESKY TEAM and its moderation efforts (favor), criticizing them (against), or neither (none). If the post's opinion is not directed towards the Bluesky team's moderation approach, even if it's on-topic, indicate that the opinion is 'none'.

Guide the user through your classification step by step, citing specific quotes from the text."""

        OUTPUT_SCHEMA: JSONSchema = {
            "name": "opinion_mining",
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

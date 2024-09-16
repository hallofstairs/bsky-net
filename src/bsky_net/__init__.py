import json
import sys
import time
import typing as t

T = t.TypeVar("T")


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
                sys.stdout.write(f"\r{i+1}")
                sys.stdout.flush()

        yield item


Post = t.TypedDict(
    "Post",
    {
        "$type": t.Literal["app.bsky.feed.post"],
        "did": str,
        "uri": str,
        "text": str,
        "createdAt": str,
        "reply": t.Optional[dict[str, dict]],
        "embed": t.Optional[dict[str, t.Any]],
    },
)


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


def records(
    stream_path: str,
    start_date: str = "2022-11-17",
    end_date: str = "2023-05-01",
    log: bool = True,
) -> t.Generator[t.Any, None, None]:
    """
    Generator that yields records from the stream for the given date range.

    End date is inclusive.
    """
    for record in tq(jsonl[t.Any].iter(stream_path), active=log):
        if record["createdAt"] >= start_date and record["createdAt"] <= end_date:
            yield record


def did_from_uri(uri: str) -> t.Optional[str]:
    if not uri:
        print("\nMisformatted URI (empty string)")
        return None

    try:
        return uri.split("/")[2]
    except Exception:
        print("\nMisformatted URI: ", uri)
        return None

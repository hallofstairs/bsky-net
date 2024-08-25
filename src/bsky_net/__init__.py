import json
import typing as t
from datetime import datetime, timedelta

from bsky_net.utils import tq


def generate_timestamps(start_date: str, end_date: str) -> list[str]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    delta = end_dt - start_dt

    return [
        (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(delta.days + 1)
    ]


def records(
    stream_dir: str, start_date: str = "2022-11-17", end_date: str = "2023-05-01"
) -> t.Generator[dict[str, t.Any], None, None]:
    """
    Generator that yields records from the stream for the given date range.

    End date is inclusive.
    """
    for ts in tq(generate_timestamps(start_date, end_date)):
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

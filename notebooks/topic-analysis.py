# %% Imports

import datetime
import os
import typing as t

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pydantic import BaseModel, ValidationError

from bsky_net import Post, jsonl, records

# Constants
BATCH_DIR = "../data/batches/cot-moderation-2023-05-24_2023-05-28"
STREAM_DIR = "../data/raw/stream-2023-07-01"

# %% Helpers


class Reasoning(BaseModel):
    quote: str
    conclusion: str


class StanceClassification(BaseModel):
    on_topic: bool
    reasoning: list[Reasoning]


def extract_quoted_uri(post: Post) -> t.Optional[str]:
    if "embed" not in post or not post["embed"]:
        return None

    try:
        if post["embed"]["$type"] == "app.bsky.embed.record":
            return post["embed"]["record"]["uri"]
        elif post["embed"]["$type"] == "app.bsky.embed.recordWithMedia":
            return post["embed"]["record"]["record"]["uri"]
    except KeyError:
        return None


# %% Extract on-topic posts

on_topic_uris: set[str] = set()
count = 0

for file in sorted(os.listdir(f"{BATCH_DIR}/out")):
    path = f"{BATCH_DIR}/out/{file}"

    for obj in jsonl[dict].iter(path):
        try:
            res = StanceClassification.model_validate_json(
                obj["response"]["body"]["choices"][0]["message"]["content"]
            )
        except ValidationError:
            continue

        if res.on_topic:
            on_topic_uris.add(obj["custom_id"])

        count += 1

print(
    f"{count} total posts, {len(on_topic_uris)} on-topic ({len(on_topic_uris) / count * 100:.2f}%)"
)

# %% Label related posts (quotes, replies)


class TaggedPost(BaseModel):
    uri: str
    createdAt: str
    did: str
    on_topic: bool
    text: str


posts: list[TaggedPost] = []

# Create post ref
for record in records(STREAM_DIR, start_date="2023-05-24", end_date="2023-05-28"):
    if record["$type"] != "app.bsky.feed.post":
        continue

    post = record

    on_topic = False

    # Assign replies label of root
    if "reply" in post and post["reply"]:
        if post["reply"]["root"]["uri"] in on_topic_uris:
            on_topic = True

    # Assign quotes label of subject
    if "embed" in post and post["embed"]:
        subject_uri = extract_quoted_uri(post)

        if not subject_uri:  # Not a quote post
            continue

        if subject_uri in on_topic_uris:
            on_topic = True

    if post["uri"] in on_topic_uris:
        # print(post["text"])
        # print("-" * 20)
        on_topic = True

    posts.append(
        TaggedPost(
            uri=post["uri"],
            createdAt=post["createdAt"],
            did=post["did"],
            on_topic=on_topic,
            text=post["text"],
        )
    )


# %% Analysis


counts: dict[str, dict] = {}

for post in posts:
    created_at = datetime.datetime.fromisoformat(post.createdAt).astimezone(
        datetime.timezone.utc
    )

    # Hourly counts
    time = created_at.replace(minute=0, second=0, microsecond=0).isoformat()

    if time not in counts:
        counts[time] = {
            "off_topic": 0,
            "on_topic": 0,
            "total": 0,
        }

    category = "on_topic" if post.on_topic else "off_topic"

    counts[time][category] += 1
    counts[time]["total"] += 1

# Sort counts by key (timestamp)
sorted_counts = dict(sorted(counts.items()))

# Convert the sorted_counts to a DataFrame for easier plotting
df = pd.DataFrame(sorted_counts).T
df.index = pd.to_datetime(df.index)
df["on_topic_pct"] = df["on_topic"] / df["total"] * 100
df = df[df.index < pd.Timestamp("2023-05-29", tz=datetime.timezone.utc)]

# %% Plot

sns.set_style("white")
sns.set_context("poster")

fig, ax = plt.subplots(figsize=(16, 9))
sns.lineplot(x=df.index, y=df["on_topic_pct"], ax=ax)

ax.set_title("Percentage of Posts Related to Bluesky Moderation Decisions")
ax.set_xlabel("Time")
ax.set_ylabel("Percentage of Posts")

sns.despine()

plt.tight_layout()
plt.show()

print("Total posts during period:", df["total"].sum())
print(
    f"On-topic posts during period: {df['on_topic'].sum()} ({df['on_topic'].sum() / df['total'].sum() * 100:.2f}%)"
)

# %% Imports

import datetime
import os
import typing as t

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import DateFormatter

from bsky_net import Post
from bsky_net.utils import jsonl

# Constants
BATCH_DIR = "../data/batches/moderation-2023-05-24_2023-05-28"
POSTS_PATH = "../data/raw/posts/posts-2023-07-01.jsonl"

# TODO: second pass with GPT 4o


def get_topic(message: str) -> t.Literal[0, 1, -1]:
    if "1" in message:
        return 1
    elif "0" in message:
        return 0
    else:
        return -1


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


def rkey_from_uri(uri: str) -> str:
    return uri.split("/")[-1]


# %% Aggregate output files, hydrate with post info

labels_ref: dict[str, int] = {}

for file in sorted(os.listdir(f"{BATCH_DIR}/out")):
    path = f"{BATCH_DIR}/out/{file}"

    for obj in jsonl[dict].iter(path):
        message: str = obj["response"]["body"]["choices"][0]["message"]["content"]
        topic = get_topic(message)

        labels_ref[obj["custom_id"]] = topic

START_URI = "at://did:plc:yl7wcldipsfnjdww2jg5mnrv/app.bsky.feed.post/3jwj5rqybfc2o"
END_URI = "at://did:plc:zyrricadyhmzfjw6didjrwio/app.bsky.feed.post/3jwkurtzs6c2a"

posts = []
in_range = False

# Create post ref
for post in jsonl[Post].iter(POSTS_PATH):
    if post["uri"] == START_URI:
        print("In range: ", post["uri"])
        in_range = True

    if not in_range:
        continue

    if post["uri"] == END_URI:
        break

    # Assign replies label of root
    if "reply" in post and post["reply"]:
        label = labels_ref.get(post["reply"]["root"]["uri"])

        if label is None:
            continue

    # Assign quotes label of subject
    elif "embed" in post and post["embed"]:
        subject_uri = extract_quoted_uri(post)

        # Not a quote post
        if not subject_uri:
            continue

        label = labels_ref.get(subject_uri)

        if label is None:
            continue

    else:
        label = labels_ref.get(post["uri"])

        if label is None:
            continue

    posts.append(
        {
            "uri": post["uri"],
            "createdAt": post["createdAt"],
            "did": post["did"],
            "classification": label,
            "text": post["text"],
        }
    )


# %% Analysis


counts: dict[str, dict[int, int]] = {}

for post in posts:
    created_at = datetime.datetime.fromisoformat(post["createdAt"]).astimezone(
        datetime.timezone.utc
    )
    # print(created_at)

    # Hourly counts
    time = created_at.replace(minute=0, second=0, microsecond=0).isoformat()

    if time not in counts:
        counts[time] = {
            0: 0,
            1: 0,
            -1: 0,
        }

    counts[time][post["classification"]] += 1

# Sort counts by key (timestamp)
sorted_counts = dict(sorted(counts.items()))

for time, splits in sorted_counts.items():
    total = sum(splits.values())

    print(time, f"{(splits[1] / total * 100):.2f}%")


# Convert the sorted_counts to a DataFrame for easier plotting
df = pd.DataFrame(sorted_counts).T
df.index = pd.to_datetime(df.index)
df["positive_percentage"] = df[1] / df.sum(axis=1) * 100

# Create the plot
plt.figure(figsize=(12, 6))
plt.plot(df.index, df["positive_percentage"])

# Customize the plot
plt.title("Percentage of Related to Moderation Decisions")
plt.xlabel("Time")
plt.ylabel("Percentage of Posts")

# Format x-axis to show dates nicely
plt.gca().xaxis.set_major_formatter(DateFormatter("%b %d, %I%p"))
plt.gcf().autofmt_xdate()  # Rotate and align the tick labels

# Show the plot
plt.tight_layout()
plt.show()

# %% Make posts ref

posts_ref: dict[str, Post] = {}

for post in jsonl[Post].iter(POSTS_PATH):
    posts_ref[post["uri"]] = post

# %% Print all relevant posts

count = 0
for file in sorted(os.listdir(f"{BATCH_DIR}/out")):
    path = f"{BATCH_DIR}/out/{file}"

    for obj in jsonl[dict].iter(path):
        message: str = obj["response"]["body"]["choices"][0]["message"]["content"]
        topic = get_topic(message)

        post = posts_ref[obj["custom_id"]]

        if topic == 1:
            count += 1
            print(post["text"])
            print("-" * 40)
            print()

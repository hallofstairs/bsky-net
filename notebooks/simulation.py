# %% Imports

import json
import os
import random
import typing as t
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from bsky_net import TimeFormat, tq

# %% Helpers

ExpressedOpinion = t.Literal["favor", "against", "none"]
InternalOpinion = t.Literal["favor", "against"]
Label = tuple[str, ExpressedOpinion]


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


BskyNetGraph: t.TypeAlias = dict[str, dict[str, UserActivity]]


class BskyNet:
    def __init__(self, path: str) -> None:
        self.path = path
        self.time_steps = self.calc_time_steps()

    def simulate(
        self,
    ) -> t.Generator[tuple[int, dict[str, UserActivity]], None, None]:
        for i, time_step in enumerate(tq(sorted(os.listdir(self.path)))):
            with open(f"{self.path}/{time_step}", "r") as json_file:
                yield i, json.load(json_file)

    def calc_time_steps(self) -> list[str]:
        return [Path(f).stem for f in sorted(os.listdir(self.path))]

    def get_opinions(
        self, topic: str, records: dict[str, LabeledRecord]
    ) -> list[ExpressedOpinion]:
        return [
            rec_opinion
            for rec in records.values()
            for rec_topic, rec_opinion in rec["labels"]
            if rec_topic == topic
        ]


# %% Model examples


def majority_rule(
    opinions: list[ExpressedOpinion], curr_opinion: InternalOpinion
) -> InternalOpinion:
    counts = Counter(opinions)

    if counts["favor"] > counts["against"]:
        return "favor"
    elif counts["against"] > counts["favor"]:
        return "against"

    return curr_opinion


def random_rule(
    opinions: list[ExpressedOpinion], curr_opinion: InternalOpinion
) -> InternalOpinion:
    internal_opinions: list[InternalOpinion] = [
        opinion for opinion in opinions if opinion != "none"
    ]
    if not internal_opinions:
        return curr_opinion

    return random.choice(internal_opinions)


# %% Simulate

bsky_net = BskyNet("../data/processed/bsky-net-daily")
time_steps = bsky_net.time_steps

# NOTE: bsky-net currently ignores: replies, quotes, non-english posts, etc
# TODO: bsky-net is wrong for some reason?

# Initialize empty opinion states
internal_opinions: dict[str, InternalOpinion] = {}

# Initialize opinion history log (for plotting)
history: dict[str, list[int]] = {
    "favor": [0] * len(time_steps),
    "against": [0] * len(time_steps),
    "total_opinions": [0] * len(time_steps),
    "total_posts": [0] * len(time_steps),
    "moderation_posts": [0] * len(time_steps),
    "expressed_match": [0] * len(time_steps),
    "expressed_total": [0] * len(time_steps),
}

# Iterate over each time step
for step, active_users in bsky_net.simulate():
    existing_users = set(internal_opinions.keys())
    new_users = set(active_users.keys()) - existing_users

    # Initialize new users with random opinions
    for user_id in new_users:
        internal_opinions[user_id] = random.choice(["favor", "against"])

    all_posts: set[str] = set()
    moderation_posts: set[str] = set()

    # Iterate over all users
    for did in internal_opinions:
        # User didn't have any activity during time step -- keep opinion the same
        if did not in active_users:
            history[internal_opinions[did]][step] += 1
            continue

        # Get user's activity during time step -- posts observed, created, liked
        activity = active_users[did]

        # Get opinions expressed by neighbors
        observed_moderation_opinions: list[ExpressedOpinion] = bsky_net.get_opinions(
            topic="moderation", records=activity["seen"]
        )

        # Get opinions expressed by user: "ground truth"
        expressed_moderation_opinions: list[ExpressedOpinion] = bsky_net.get_opinions(
            topic="moderation", records=activity["posted"]
        )

        # LOGGING -- for plotting
        all_posts.update(activity["posted"].keys())
        for uri, post in activity["posted"].items():
            for topic, _ in post["labels"]:
                if topic == "moderation":
                    moderation_posts.add(uri)

        # User observed no opinions -- don't update
        if not observed_moderation_opinions:
            history[internal_opinions[did]][step] += 1
            continue

        # Get user's current opinion
        current_opinion = internal_opinions[did]

        # Update user's current opinion using majority rule
        pred_opinion = majority_rule(observed_moderation_opinions, current_opinion)

        # Check accuracy of model prediction against "ground truth" expressed opinion
        if expressed_moderation_opinions:
            true_opinion = majority_rule(expressed_moderation_opinions, current_opinion)
            history["expressed_match"][step] += 1 if pred_opinion == true_opinion else 0
            history["expressed_total"][step] += 1

        # Update opinion state
        internal_opinions[did] = pred_opinion

        # LOGGING
        history[pred_opinion][step] += 1

    # MORE LOGGING
    history["total_opinions"][step] = len(internal_opinions)
    history["total_posts"][step] = len(all_posts)
    history["moderation_posts"][step] = len(moderation_posts)

print(
    f"Breakdown of opinions at t={time_steps[-1]}: {json.dumps(Counter(internal_opinions.values()), indent=2)}"
)

start_day = "2023-04-10"
start_idx = time_steps.index(start_day)
time_steps_trunc = time_steps[start_idx:]

for key, value in history.items():
    history[key] = value[start_idx:]

# %% Plot results

subplot: tuple[Figure, list[Axes]] = plt.subplots(4, 1, figsize=(10, 20))
fig, axs = subplot

history_norm = {
    "favor": [
        count / history["total_opinions"][idx]
        if history["total_opinions"][idx] != 0
        else 0
        for idx, count in enumerate(history["favor"])
    ],
    "against": [
        count / history["total_opinions"][idx]
        if history["total_opinions"][idx] != 0
        else 0
        for idx, count in enumerate(history["against"])
    ],
}

# Plot normalized opinions
axs[0].plot(time_steps_trunc, history_norm["favor"], label="favor", color="tab:blue")
axs[0].plot(time_steps_trunc, history_norm["against"], label="against", color="tab:red")
axs[0].set_xlabel("Day")
axs[0].set_ylabel("Percentage")
axs[0].set_title("Moderation Opinion Distribution (Majority Rule model)")
axs[0].legend()
axs[0].set_ylim(0, 1)
axs[0].set_xticks(time_steps_trunc[::3])
axs[0].tick_params(axis="x", rotation=45)

model_accuracy = [
    count / history["expressed_total"][idx]
    if history["expressed_total"][idx] != 0
    else 0
    for idx, count in enumerate(history["expressed_match"])
]

# Plot accuracy of opinion model in predicting expressed opinions
axs[1].plot(time_steps_trunc, model_accuracy, color="tab:green")
axs[1].set_xlabel("Day")
axs[1].set_ylabel("Accuracy")
axs[1].set_title("Accuracy (Majority Rule Model)")
axs[1].set_ylim(0, 1)
axs[1].set_xticks(time_steps_trunc[::3])
axs[1].tick_params(axis="x", rotation=45)

post_volume_norm = [
    count / history["total_posts"][idx] if history["total_posts"][idx] != 0 else 0
    for idx, count in enumerate(history["moderation_posts"])
]

# Plot volume of posts
axs[2].plot(time_steps_trunc, post_volume_norm, color="tab:orange")
axs[2].set_xlabel("Day")
axs[2].set_ylabel("Percentage")
axs[2].set_title("Percentage of All Bluesky Posts Discussing Moderation")
axs[2].set_ylim(0, 0.25)
axs[2].set_xticks(time_steps_trunc[::3])
axs[2].tick_params(axis="x", rotation=45)

# Plot total users
# axs[2].plot(time_steps_trunc, history["total_opinions"], color="tab:orange")
# axs[2].set_xlabel("Day")
# axs[2].set_ylabel("Count")
# axs[2].set_title("Total Users with Moderation Opinions (using Majority Rule)")
# axs[2].set_xticks(time_steps_trunc[::10])
# axs[2].tick_params(axis="x", rotation=45)

# Total posts on Bluesky
ax3_2 = axs[3].twinx()
axs[3].plot(
    time_steps_trunc,
    history["moderation_posts"],
    color="tab:purple",
    label="Moderation-Focused Posts",
)
ax3_2.plot(
    time_steps_trunc,
    history["total_posts"],
    color="tab:orange",
    label="All Posts",
)
ax3_2.set_ylabel("Total Count (All Posts)", color="tab:orange")
axs[3].set_xlabel("Day")
axs[3].set_ylabel("Moderation-Focused Count", color="tab:purple")
axs[3].set_title("Daily Bluesky Posts")
axs[3].set_xticks(time_steps_trunc[::3])
axs[3].tick_params(axis="x", rotation=45)

# Set the colors for the y-axis labels to match the lines
axs[3].tick_params(axis="y", labelcolor="tab:purple")
ax3_2.tick_params(axis="y", labelcolor="tab:orange")

# Combine legends
lines, labels = axs[3].get_legend_handles_labels()
lines2, labels2 = ax3_2.get_legend_handles_labels()
ax3_2.legend(lines + lines2, labels + labels2, loc="upper left")

plt.tight_layout()
plt.show()

# %% See how often expressed differs from internal

PAUL_DID = "did:plc:ragtjsm2j2vknwkz3zp4oxrd"
STORE_BRAND_DID = "did:plc:tr3nhnia67b45zjocyyplqd7"

did = STORE_BRAND_DID
post_counts = Counter()
internal_opinion_log = []
current_opinion: InternalOpinion = "favor"

for step, data in bsky_net.items():
    if did in data:
        seen = data[did]["seen"]
        posted = data[did]["posted"]

        observed_opinions: list[ExpressedOpinion] = [
            post_opinion
            for record in seen.values()
            for post_topic, post_opinion in record["labels"]
            if post_topic == "moderation"
        ]
        expressed_opinions: list[ExpressedOpinion] = [
            post_opinion
            for record in posted.values()
            for post_topic, post_opinion in record["labels"]
            if post_topic == "moderation"
        ]

        # true_opinion = majority_rule(expressed_opinions, "none")
        # pred_opinion = majority_rule(observed_opinions, "none")
        # print((step, pred_opinion, true_opinion))
        print("expressed opinions: ", json.dumps(Counter(expressed_opinions), indent=2))
        print("observed opinions: ", json.dumps(Counter(observed_opinions), indent=2))

        # print([post["text"] for post in user_posts.values()])

        # opinions = [post["opinion"] for post in user_posts.values()]
        # internal_opinion_log.append(opinions)

# %% Imports

import json
import random
import typing as t
from collections import Counter

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from bsky_net import TimeFormat

# %% Helpers

ExpressedOpinion = t.Literal["favor", "against", "none"]
InternalOpinion = t.Literal["favor", "against"]

Label = tuple[str, ExpressedOpinion]


class LabeledRecord(t.TypedDict):
    labels: list[Label]
    createdAt: str


class LabeledPost(LabeledRecord):
    text: str


class UserActivity(t.TypedDict):
    seen: dict[str, LabeledRecord]
    posted: dict[str, LabeledPost]
    liked: dict[str, LabeledRecord]


BskyNetGraph: t.TypeAlias = dict[str, dict[str, UserActivity]]


# %% Load graph from data/processed

time_step_size = TimeFormat.daily

with open(f"../data/processed/bsky-net-{time_step_size.name}.json", "r") as json_file:
    bsky_net: BskyNetGraph = json.load(json_file)


# %% Simulate


def majority_rule(
    opinions: list[ExpressedOpinion], curr_opinion: InternalOpinion
) -> InternalOpinion:
    counts = Counter(opinions)

    if counts["favor"] > counts["against"]:
        return "favor"
    elif counts["against"] > counts["favor"]:
        return "against"

    return curr_opinion


time_steps = list(bsky_net.keys())

# Initialize empty opinion states
internal_opinions: dict[str, InternalOpinion] = {}

# Initialize opinion history log (for plotting)
history: dict[str, list[int]] = {
    "favor": [0] * len(time_steps),
    "against": [0] * len(time_steps),
    "total_users": [0] * len(time_steps),
    "total_posts": [0] * len(time_steps),
    "moderation_posts": [0] * len(time_steps),
}

# TODO: See how often the expressed opinion differs from the internal one

# Iterate over each time step
for step, active_users in enumerate(bsky_net.values()):
    existing_users = set(internal_opinions.keys())
    new_users = set(active_users.keys()) - existing_users

    # Initialize new users with random opinions
    for user_id in new_users:
        internal_opinions[user_id] = random.choice(["favor", "against"])

    seen_moderation_posts = set()
    seen_posts = set()

    # Iterate over all users
    for did in internal_opinions:
        # If user didn't see any posts, keep their opinion the same
        if did not in active_users:
            history[internal_opinions[did]][step] += 1
            continue

        # If a user sees posts, update their opinion based on majority vote
        activity = active_users[did]

        # Get the opinions expressed by neighbors
        moderation_opinions: list[ExpressedOpinion] = []
        for uri, post in activity["seen"].items():
            seen_posts.add(uri)
            for label in post["labels"]:
                if label[0] == "moderation":
                    moderation_opinions.append(label[1])
                    seen_moderation_posts.add(uri)

        # Get user's current opinion
        current_opinion = internal_opinions[did]

        # Update user's opinion using majority rule
        new_opinion = majority_rule(moderation_opinions, current_opinion)

        # Log opinions, history
        internal_opinions[did] = new_opinion
        history[new_opinion][step] += 1

    history["total_users"][step] = len(internal_opinions)
    history["total_posts"][step] = len(seen_posts)
    history["moderation_posts"][step] = len(seen_moderation_posts)

print(
    f"Breakdown of opinions at t={time_steps[-1]}: {json.dumps(Counter(internal_opinions.values()), indent=2)}"
)


# %% Plot results

history_norm = {
    "favor": [
        count / history["total_users"][idx] if history["total_users"][idx] != 0 else 0
        for idx, count in enumerate(history["favor"])
    ],
    "against": [
        count / history["total_users"][idx] if history["total_users"][idx] != 0 else 0
        for idx, count in enumerate(history["against"])
    ],
}

post_volume_norm = [
    count / history["total_posts"][idx] if history["total_posts"][idx] != 0 else 0
    for idx, count in enumerate(history["moderation_posts"])
]

subplot: tuple[Figure, list[Axes]] = plt.subplots(4, 1, figsize=(10, 20))
fig, axs = subplot

# Plot volume of posts
axs[0].plot(time_steps, post_volume_norm, color="tab:orange")
axs[0].set_xlabel("Day")
axs[0].set_ylabel("Percentage")
axs[0].set_title("Percentage of Moderation-Related Posts")
axs[0].set_xticks(time_steps[::10])
axs[0].tick_params(axis="x", rotation=45)

# Plot normalized opinions
axs[1].plot(time_steps, history_norm["favor"], label="favor", color="tab:blue")
axs[1].plot(time_steps, history_norm["against"], label="against", color="tab:red")
axs[1].set_xlabel("Day")
axs[1].set_ylabel("Percentage")
axs[1].set_title("Moderation Opinion Distribution (using Majority Rule)")
axs[1].legend()
axs[1].set_xticks(time_steps[::10])
axs[1].tick_params(axis="x", rotation=45)

# Plot total users
axs[2].plot(time_steps, history["total_users"], color="tab:orange")
axs[2].set_xlabel("Day")
axs[2].set_ylabel("Count")
axs[2].set_title("Cumulative Users on Bluesky")
axs[2].set_xticks(time_steps[::10])
axs[2].tick_params(axis="x", rotation=45)

# Total posts on Bluesky
axs[3].plot(
    time_steps,
    history["moderation_posts"],
    color="tab:green",
    label="Moderation-Focused Posts",
)
ax3_2 = axs[3].twinx()
ax3_2.plot(time_steps, history["total_posts"], color="tab:orange", label="All Posts")
ax3_2.set_ylabel("Total Count")

axs[3].set_xlabel("Day")
axs[3].set_ylabel("Moderation-Focused Count")
axs[3].set_title("Daily Bluesky Posts")
axs[3].set_xticks(time_steps[::10])
axs[3].tick_params(axis="x", rotation=45)

# Combine legends
lines, labels = axs[3].get_legend_handles_labels()
lines2, labels2 = ax3_2.get_legend_handles_labels()
ax3_2.legend(lines + lines2, labels + labels2, loc="upper left")

plt.tight_layout()
plt.show()

# %% See how often expressed differs from internal
PAUL_DID = "did:plc:ragtjsm2j2vknwkz3zp4oxrd"
STORE_BRAND_DID = ""

post_counts = Counter()
internal_opinion_log = []

for step, data in bsky_net.items():
    for did, activity in data.items():
        post_counts[did] += len(activity["posted"])
        # print([post["text"] for post in user_posts.values()])

        # opinions = [post["opinion"] for post in user_posts.values()]
        # internal_opinion_log.append(opinions)


# %%

opinionated_posts = {"favor": [], "against": [], "none": []}

for step, data in bsky_net.items():
    for did, activity in data.items():
        for uri, post in activity["posted"].items():
            for topic, opinion in post["labels"]:
                if topic == "moderation":
                    opinionated_posts[opinion].append(f"{post["text"]} - {uri}")

# %% Imports

import json
import random
from collections import Counter

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from bsky_net import BskyNet, ExpressedBelief, InternalBelief

# %% Model examples


def majority_rule(
    beliefs: list[ExpressedBelief], curr_belief: InternalBelief
) -> InternalBelief:
    counts = Counter(beliefs)

    if counts["favor"] > counts["against"]:
        return "favor"
    elif counts["against"] > counts["favor"]:
        return "against"

    return curr_belief


def random_rule(
    beliefs: list[ExpressedBelief], curr_belief: InternalBelief
) -> InternalBelief:
    internal_beliefs: list[InternalBelief] = [
        belief for belief in beliefs if belief != "none"
    ]
    if not internal_beliefs:
        return curr_belief

    return random.choice(internal_beliefs)


# %% Simulate

bsky_net = BskyNet("../data/processed/bsky-net-daily")
time_steps = bsky_net.time_steps

topical = 0
total = 0

for step, active_users in bsky_net.simulate():
    all_posts: set[str] = set()

    for did, activity in active_users.items():
        for post, data in activity["posted"].items():
            total += 1

            if len(data["labels"]) > 0:
                topical += 1

# %%

# NOTE: bsky-net currently ignores: replies, quotes, non-english posts, etc

# Initialize empty belief states
internal_beliefs: dict[str, InternalBelief] = {}

# Initialize belief history log (for plotting)
history: dict[str, list[int]] = {
    "favor": [0] * len(time_steps),
    "against": [0] * len(time_steps),
    "total_beliefs": [0] * len(time_steps),
    "total_posts": [0] * len(time_steps),
    "moderation_posts": [0] * len(time_steps),
    "expressed_match": [0] * len(time_steps),
    "expressed_total": [0] * len(time_steps),
}

# Iterate over each time step
for step, active_users in bsky_net.simulate():
    existing_users = set(internal_beliefs.keys())
    new_users = set(active_users.keys()) - existing_users

    # Initialize new users with random beliefs
    for user_id in new_users:
        internal_beliefs[user_id] = random.choice(["favor", "against"])

    all_posts: set[str] = set()
    moderation_posts: set[str] = set()

    # Iterate over all users
    for did in internal_beliefs:
        # User didn't have any activity during time step -- keep belief the same
        if did not in active_users:
            history[internal_beliefs[did]][step] += 1
            continue

        # Get user's activity during time step -- posts observed, created, liked
        activity = active_users[did]

        # Get beliefs expressed by neighbors
        observed_moderation_beliefs = bsky_net.get_beliefs(
            topic="moderation", records=activity["seen"]
        )

        # Get beliefs expressed by user: "ground truth"
        expressed_moderation_beliefs = bsky_net.get_beliefs(
            topic="moderation", records=activity["posted"]
        )

        # LOGGING -- for plotting
        all_posts.update(activity["posted"].keys())
        for uri, post in activity["posted"].items():
            for topic, _ in post["labels"]:
                if topic == "moderation":
                    moderation_posts.add(uri)

        # User observed no beliefs -- don't update
        if not observed_moderation_beliefs:
            history[internal_beliefs[did]][step] += 1
            continue

        # Get user's current belief
        current_belief = internal_beliefs[did]

        # Update user's current belief using majority rule
        pred_belief = majority_rule(observed_moderation_beliefs, current_belief)

        # Check accuracy of model prediction against "ground truth" expressed belief
        if expressed_moderation_beliefs:
            true_belief = majority_rule(expressed_moderation_beliefs, current_belief)
            history["expressed_match"][step] += 1 if pred_belief == true_belief else 0
            history["expressed_total"][step] += 1

        # Update belief state
        internal_beliefs[did] = pred_belief

        # LOGGING
        history[pred_belief][step] += 1

    # MORE LOGGING
    history["total_beliefs"][step] = len(internal_beliefs)
    history["total_posts"][step] = len(all_posts)
    history["moderation_posts"][step] = len(moderation_posts)

print(
    f"Breakdown of beliefs at t={time_steps[-1]}: {json.dumps(Counter(internal_beliefs.values()), indent=2)}"
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
        count / history["total_beliefs"][idx]
        if history["total_beliefs"][idx] != 0
        else 0
        for idx, count in enumerate(history["favor"])
    ],
    "against": [
        count / history["total_beliefs"][idx]
        if history["total_beliefs"][idx] != 0
        else 0
        for idx, count in enumerate(history["against"])
    ],
}

# Plot normalized beliefs
axs[0].plot(time_steps_trunc, history_norm["favor"], label="favor", color="tab:blue")
axs[0].plot(time_steps_trunc, history_norm["against"], label="against", color="tab:red")
axs[0].set_xlabel("Day")
axs[0].set_ylabel("Percentage")
axs[0].set_title("Moderation belief Distribution (Majority Rule model)")
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

# Plot accuracy of belief model in predicting expressed beliefs
axs[1].plot(time_steps_trunc, model_accuracy, color="tab:green")
axs[1].set_xlabel("Day")
axs[1].set_ylabel("Accuracy")
axs[1].set_title("Accuracy (Majority Rule Model)")
axs[1].set_ylim(0, 1)
axs[1].set_xticks(time_steps_trunc[::3])
axs[1].tick_params(axis="x", rotation=45)

# Calculate and display average accuracy
axs[1].text(
    0.95,
    0.95,
    f"Mean Accuracy: {(sum(model_accuracy) / len(model_accuracy)):.2f}",
    transform=axs[1].transAxes,
    fontsize=12,
    verticalalignment="top",
    horizontalalignment="right",
    bbox=dict(facecolor="white", alpha=0.5),
)

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
# axs[2].plot(time_steps_trunc, history["total_beliefs"], color="tab:orange")
# axs[2].set_xlabel("Day")
# axs[2].set_ylabel("Count")
# axs[2].set_title("Total Users with Moderation beliefs (using Majority Rule)")
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
internal_belief_log = []
current_belief: InternalBelief = "favor"

for step, data in bsky_net.simulate():
    if did in data:
        seen = data[did]["seen"]
        posted = data[did]["posted"]

        observed_beliefs: list[ExpressedBelief] = [
            post_belief
            for record in seen.values()
            for post_topic, post_belief in record["labels"]
            if post_topic == "moderation"
        ]
        expressed_beliefs: list[ExpressedBelief] = [
            post_belief
            for record in posted.values()
            for post_topic, post_belief in record["labels"]
            if post_topic == "moderation"
        ]

        # true_belief = majority_rule(expressed_beliefs, "none")
        # pred_belief = majority_rule(observed_beliefs, "none")
        # print((step, pred_belief, true_belief))
        print("expressed beliefs: ", json.dumps(Counter(expressed_beliefs), indent=2))
        print("observed beliefs: ", json.dumps(Counter(observed_beliefs), indent=2))

        # print([post["text"] for post in user_posts.values()])

        # beliefs = [post["belief"] for post in user_posts.values()]
        # internal_belief_log.append(beliefs)

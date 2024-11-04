# %% [markdown]
# ---
# title: "`bsky-net` Demo: Validating a Majority Rule Model"
# execute:
#  cache: true
# jupyter: python3
# highlight-style: github
# ---

# %% [markdown]
"""

This is a rough, elementary example walkthrough. I still need to work
on the accuracy of the expressed belief classifications, and the dataset
currently excludes replies, quotes, and non-English posts. So think of this
as more of an explanation of the process than results to interpret.

Belief classification improvement will be a continuous process.
"""

# %%

# Imports
import json
import random
from collections import Counter

import matplotlib.pyplot as plt

from bsky_net import BskyNet

# %% [markdown]
"""
## Data overview

`bsky-net` is a dataset, and that dataset is just one big json file. The json file 
is broken up by time steps (days), and it describes each user's activity 
during that time step: posts they created, "saw", and liked. All of the activity
is tagged with belief labels, when possible.

"Saw" is used very loosely here; currently, "saw" is a list of every post 
created that day by an account that user followed on that day. This means that 
many posts marked as "seen" weren't _actually seen_ by that user. 

The accuracy of the "seen" list can/will be improved, using information 
like that user's activity on that day.

### Toy example

Here's a toy example of the data structure (explanation below):

```json
{
    "2023-01-01": {
        "did:plc:ragtjsm2j2vknwkz3zp4oxrd": {
            "posted": {
                "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvaoui4dk2g": {
                    "text": "$13M and not a clear use of funds or trust and safety prioritization, fuck me. I know and have so many founders who would kill for this and could never get it.",
                    "createdAt": "2023-01-01T03:34:48.600Z",
                    "labels": [
                        ["moderation", "against"]
                    ]
                },
                "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvbxavpp22u": {
                    "text": "I want to go to a library of scents. Smells trigger memories so well, more than any museum can.",
                    "createdAt": "2023-01-01T07:34:30.802Z",
                    "labels": []
                }
            },
            "seen": {},
            "liked": {}
        },
        "did:plc:o5tqfvsr5qwofe3icp7a6z6j": {
            "posted": {
                "at://did:plc:o5tqfvsr5qwofe3icp7a6z6j/app.bsky.feed.post/3jpymqtz2zt24": {
                    "text": ".zip is Google's experiment to make more money",
                    "createdAt": "2023-01-01T06:04:52.037Z",
                    "labels": []
                }
            },
            "seen": {
                "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvaoui4dk2g": {
                    "createdAt": "2023-01-01T03:34:48.600Z",
                    "labels": [
                        ["moderation", "against"]
                    ]
                },
                "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvbxavpp22u": {
                    "createdAt": "2023-01-01T07:34:30.802Z",
                    "labels": []
                }
            },
            "liked": {
                "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvaoui4dk2g": {
                    "createdAt": "2023-01-01T03:34:48.600Z",
                    "labels": [
                        ["moderation", "against"]
                    ]
                }
            }
        }
    }
}

```

On Jan 1, 2023, there were two users with activity: `did:plc:ragtjsm2j2vknwkz3zp4oxrd` and `did:plc:o5tqfvsr5qwofe3icp7a6z6j` (these are their
"DIDs", or user IDs). We'll call them User A and User B, respectively, for brevity.

On Jan 1, 2023, User A created 2 posts: `at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvaoui4dk2g` and `at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jpvbxavpp22u` (these are their "URIs", or post IDs).
Based on the text of the posts, one of them was labeled with the "moderation" topic and expressed the belief "against"
towards that topic. None of the accounts User A followed posted on Jan 1, so their 
"seen" and "liked" objects are both empty.

User B created 1 post, which had no topic/belief labels. However, User B was a follower
of User A, so their "seen" object includes the 2 posts from User A. Also, User B
liked one of User A's posts, so their "liked" obect includes that post as well.

The data structure includes a lot of duplicate data, which just makes simulation
easier. 

### Code

Below, I'll be using a helper class, `BskyNet`, to parse the (quite large) `bsky-net` json file.
All it's really doing is helping me iterate over the data structure.
"""

# %%

bsky_net = BskyNet("../data/processed/bsky-net-daily")

time_steps = bsky_net.time_steps
print(time_steps)

# %% [markdown]

"""
As seen in `bsky_net.time_steps`, the dataset currently includes all
activities on Bluesky up to May 10, 2023.

To iterate over each time step, we'll use `bsky_net.simulate()`:
"""

# %%

for step, user_activity in bsky_net.simulate(verbose=False):
    print(f"{time_steps[step]} ({len(user_activity)} users with activity)\n")
    break

# %% [markdown]
"""
## Simulating a Model

Now, we're going to use the dataset to simulate a belief dynamics model.

### Model definition

For this example, we use the classic majority rule, which is defined as follows:
"""

# %%


def majority_rule(beliefs: list[str], current_belief: str) -> str:
    """Calculate the majority belief from a list of expressed beliefs."""

    counts = Counter(beliefs)

    if counts["favor"] > counts["against"]:
        return "favor"
    elif counts["against"] > counts["favor"]:
        return "against"
    else:
        return current_belief


# %% [markdown]
"""
### Belief updating

For each time step:

1. New users to the network are initialized with a random belief
2. If a user has observed posts this time step, their belief is updated according to the
   majority rule, using that user's observed posts as "edges"
    a. If a user observed no posts, or no posts with expressed beliefs, their belief is assumed to stay the same
3. Their new belief as predicted by the model is compared against
their actual activity during that same time step, if possible
    a. Below, I simply compare the user's predicted belief with
    the majority of beliefs expressed in their posts during that time stamp. This
    is a very small $n$ size per time step, though, and can be improved
"""

# %%

# Initialize belief log (for plotting)
belief_history = {
    "favor": [0] * len(bsky_net.time_steps),
    "against": [0] * len(bsky_net.time_steps),
}

# Initialize accuracy log (for plotting)
model_accuracy = {
    "correct": [0] * len(bsky_net.time_steps),
    "total": [0] * len(bsky_net.time_steps),
}

# Track belief states
internal_beliefs: dict[str, str] = {}

# Iterate over each time step
for step, user_activity in bsky_net.simulate(verbose=False):
    # Initialize new users with random beliefs
    new_users = set(user_activity) - set(internal_beliefs.keys())
    for user_id in new_users:
        internal_beliefs[user_id] = random.choice(["favor", "against"])

    # Iterate over all current users
    for did in internal_beliefs:
        # If user doesn't have activity, don't update belief
        if did not in user_activity:
            belief_history[internal_beliefs[did]][step] += 1  # logging
            continue

        # ==== UPDATING BELIEFS ====

        # Get user's activity during time step -- posts observed, created, liked
        activity = user_activity[did]

        # Get beliefs observed by user (posted by neighbors)
        observed_moderation_beliefs = bsky_net.get_beliefs(
            topic="moderation", records=activity["seen"]
        )

        # User observed no expressed beliefs -- don't update
        if not observed_moderation_beliefs:
            belief_history[internal_beliefs[did]][step] += 1  # logging
            continue

        # Get user's current internal belief
        current_belief = internal_beliefs[did]

        # Update user's current internal belief using majority rule
        new_belief = majority_rule(observed_moderation_beliefs, current_belief)

        # Update belief state
        internal_beliefs[did] = new_belief

        belief_history[internal_beliefs[did]][step] += 1  # logging

        # ==== VALIDATING BELIEFS (when possible) ====

        # Get beliefs expressed by user -- "ground truth"
        expressed_moderation_beliefs: list[str] = bsky_net.get_beliefs(
            topic="moderation", records=activity["posted"]
        )

        # Check predicted belief against "ground truth" expressed belief, if possible
        if expressed_moderation_beliefs:
            # Use majority of expressed beliefs that time step as "ground truth"
            true_belief = majority_rule(expressed_moderation_beliefs, current_belief)
            correct = new_belief == true_belief

            # Log for plotting
            model_accuracy["correct"][step] += correct
            model_accuracy["total"][step] += 1

print(
    f"Breakdown of beliefs at t={time_steps[-1]}: {json.dumps(Counter(internal_beliefs.values()), indent=2)}"
)

# %% [markdown]

"""
## Plotting

I truncated the data prior to April 10 for the plots because of how little data there was.
"""

# %% Plotting
# | code-fold: true
# | code-summary: "Show the code"

start_day = "2023-04-10"
start_idx = bsky_net.time_steps.index(start_day)
time_steps_trunc = bsky_net.time_steps[start_idx:]

model_accuracy["correct"] = model_accuracy["correct"][start_idx:]
model_accuracy["total"] = model_accuracy["total"][start_idx:]
belief_history["favor"] = belief_history["favor"][start_idx:]
belief_history["against"] = belief_history["against"][start_idx:]

fix, ax = plt.subplots(figsize=(8, 4))

total_opinions = [
    n_favor + n_against
    for n_favor, n_against in zip(belief_history["favor"], belief_history["against"])
]

history_norm = {
    "favor": [
        count / total_opinions[idx] if total_opinions[idx] != 0 else 0
        for idx, count in enumerate(belief_history["favor"])
    ],
    "against": [
        count / total_opinions[idx] if total_opinions[idx] != 0 else 0
        for idx, count in enumerate(belief_history["against"])
    ],
}

# Plot accuracy of belief model in predicting expressed beliefs
ax.plot(time_steps_trunc, history_norm["favor"], label="favor", color="tab:blue")
ax.plot(time_steps_trunc, history_norm["against"], label="against", color="tab:red")
ax.set_xlabel("Day")
ax.set_ylabel("Percentage")
ax.set_title("Moderation Opinion Distribution (per Majority Rule Model)")
ax.legend()
ax.set_ylim(0, 1)
ax.set_xticks(time_steps_trunc[::3])
ax.tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.show()

# %%
# | code-fold: true
# | code-summary: "Show the code"

fix, ax = plt.subplots(figsize=(8, 4))

accuracy = [
    n_correct / model_accuracy["total"][i] if model_accuracy["total"][i] else 0
    for i, n_correct in enumerate(model_accuracy["correct"])
]

# Plot accuracy of belief model in predicting expressed beliefs
ax.plot(time_steps_trunc, accuracy, color="tab:green", label="Model Accuracy")
ax.axhline(y=0.5, color="red", linestyle="--", label="Random Guessing")
ax.set_xlabel("Day")
ax.set_ylabel("Accuracy")
ax.set_title("Accuracy of Majority Rule Model")
ax.legend()
ax.set_ylim(0, 1)
ax.set_xticks(time_steps_trunc[::3])
ax.tick_params(axis="x", rotation=45)
ax.text(
    0.95,
    0.95,
    f"Mean Accuracy: {(sum(accuracy) / len(accuracy)):.2f}",
    transform=ax.transAxes,
    fontsize=12,
    verticalalignment="top",
    horizontalalignment="right",
    bbox=dict(facecolor="white", alpha=0.5),
)

plt.tight_layout()
plt.show()

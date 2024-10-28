# %% Imports

import json
import typing as t
from collections import Counter

import matplotlib.pyplot as plt

# %% Helpers


class RecordInfo(t.TypedDict):
    opinion: str
    createdAt: str


class UserActivity(t.TypedDict):
    seen: dict[str, RecordInfo]
    liked: dict[str, RecordInfo]


BskyNetGraph: t.TypeAlias = dict[str, dict[str, UserActivity]]

# %% Load graph from data/processed

with open("../data/processed/bsky-net-test-daily.json", "r") as json_file:
    bsky_net: BskyNetGraph = json.load(json_file)


# %% Simulate


def majority_vote(records: list[RecordInfo]) -> str:
    counts = Counter(record["opinion"] for record in records)
    return max(counts, key=lambda x: counts[x])


opinion_history: dict[str, dict[str, dict[str, t.Optional[str]]]] = {}
# prev_step = ""

for step, data in bsky_net.items():
    opinion_history[step] = {}

    for did, activity in data.items():
        if not activity["seen"]:
            continue

        # prev_opinion = opinion_history.get(prev_step, {}).get(did, "none")

        pred_opinion = majority_vote(list(activity["seen"].values()))
        true_opinion = (
            majority_vote(list(activity["liked"].values()))
            if activity["liked"]
            else None
        )

        opinion_history[step][did] = {"true": true_opinion, "pred": pred_opinion}
        # prev_step = step

# %% Plot

steps = sorted(opinion_history.keys())[-4:]
opinions = ["favor", "against", "none"]


opinion_counts = {
    "favor": [],
    "against": [],
    "none": [],
}

for step in steps[-4:]:
    step_counts = Counter()

    for did, opinion in opinion_history[step].items():
        pred_opinion = opinion["pred"]

        if pred_opinion:
            step_counts[pred_opinion] += 1
            step_counts["total"] += 1

    for opinion in opinions:
        if step_counts["total"] > 0:
            opinion_counts[opinion].append(
                step_counts[opinion] / step_counts["total"] * 100
            )
        else:
            opinion_counts[opinion].append(0)


plt.figure(figsize=(10, 6))

for opinion in opinions:
    plt.plot(steps, opinion_counts[opinion], label=opinion)

plt.xlabel("Time Step")
plt.ylabel("Percentage")
plt.title("Opinion History Over Time")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# %%

# Evaluation calculations - when true is not None, how often do pred and true agree

total_evaluations = 0
agreement_count = 0

for step in opinion_history:
    for did, opinions in opinion_history[step].items():
        true_opinion = opinions["true"]
        pred_opinion = opinions["pred"]

        if true_opinion is not None:
            total_evaluations += 1
            if true_opinion == pred_opinion:
                agreement_count += 1

if total_evaluations > 0:
    agreement_percentage = (agreement_count / total_evaluations) * 100
else:
    agreement_percentage = 0

print(f"Total evaluations: {total_evaluations}")
print(f"Agreements: {agreement_count}")
print(f"Agreement percentage: {agreement_percentage:.2f}%")

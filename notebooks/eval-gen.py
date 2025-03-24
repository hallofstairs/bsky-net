# %% Imports

import random

import pandas as pd

from bsky_net import Post, jsonl, records

STREAM_PATH = "../data/raw/en-stream-2023-07-01"
EVAL_PATH = "../evals/stance-eval-01.csv"
END_DATE = "2023-07-01"
TOTAL_POSTS = 1_000_000  # Estimate

# %% Randomly sample 1000 posts, including hard-coded posts from old eval

# WARNING: ONLY RUN THIS ONCE

# Get hard-coded URIs from old eval
BSKY_TEST_PATH = "../data/experiments/test-set-v1.jsonl"
hard_coded_uris = set()

for post in jsonl[Post].iter(BSKY_TEST_PATH):
    hard_coded_uris.add(post["uri"])

# Randomly sample 1000 posts from the stream
random.seed(42)
sample_posts: list[Post] = []

for record in records(stream_path=STREAM_PATH, end_date=END_DATE):
    if record["$type"] == "app.bsky.feed.post":
        post: Post = record

        # Ignore replies (for now)
        if "reply" in post and post["reply"]:
            continue

        # Ignore embeds (for now)
        if "embed" in post and post["embed"]:
            continue

        # Pull 1000 posts
        if random.random() < (1000 / TOTAL_POSTS) or post["uri"] in hard_coded_uris:
            sample_posts.append(post)

        if len(sample_posts) >= 1000:
            break

# Create initial dataframe from sample posts
df = pd.DataFrame(
    [
        {
            "uri": post["uri"],
            "did": post["did"],
            "createdAt": post["createdAt"],
            "text": post["text"],
            "label": pd.NA,
            "reasoning": pd.NA,
        }
        for post in sample_posts
    ]
)

df.to_csv(EVAL_PATH, index=False)

# %% Add labels to existing eval

df = pd.read_csv(EVAL_PATH)

labels_dict = {"f": "favor", "a": "against", "n": "none", "u": "unrelated"}

# Get unlabeled posts
unlabeled_df = df[df["label"].isna()]


# Iterate through unlabeled posts
for idx, record in unlabeled_df.iterrows():
    print("\nPost:", record["text"])
    print("\nStance options:")
    print("f: Favor")
    print("a: Against")
    print("n: None")
    print("u: Unrelated")
    print("q: Quit")

    while True:
        label: str = input("\nEnter label (f/a/n/q): ")

        if label == "q":
            print("Labeling stopped")
            break

        if label in ["f", "a", "n", "u"]:
            reasoning: str = input("Enter reasoning: ")

            # Update label and reasoning in main dataframe
            df.at[idx, "label"] = labels_dict[label]
            df.at[idx, "reasoning"] = reasoning
            break
        else:
            print("Invalid input, please try again")

    if label == "q":
        break

    # Save after each label
    df.to_csv(EVAL_PATH, index=False)

print(f"\nLabeled {len(df[df['label'].notna()])} out of {len(df)} posts")

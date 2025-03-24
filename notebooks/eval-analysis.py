# %% Imports

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# %% Load eval

EVAL_PATH = "../evals/stance-eval-01-subset.csv"
df = pd.read_csv(EVAL_PATH)
# Map 'unrelated' to 'off-topic' in labels
df["label_new"] = df["label"].map({"unrelated": "off-topic"}).fillna(df["label"])

# Calculate accuracy for each model
for col in df.columns:
    if col.endswith("_answer"):
        model_name = col.replace("_answer", "")
        # Count nans and valid rows
        nan_count = df[col].isna().sum()
        valid_rows = df[df[col].notna()]
        accuracy = (valid_rows[col] == valid_rows["label_new"]).mean()
        print(f"{model_name}:")
        print(f"  Accuracy: {accuracy:.2%}")
        print(f"  Missing predictions: {nan_count}")

# %%

# Sample equal amounts from each label type
balanced_df = pd.concat(
    [
        df[df["label_new"] == label].sample(
            n=min(20, len(df[df["label_new"] == label])), random_state=42
        )
        for label in df["label_new"].unique()
    ]
)

print("\nOriginal label distribution:")
print(df["label_new"].value_counts())

print("\nBalanced label distribution:")
print(balanced_df["label_new"].value_counts())

for col in balanced_df.columns:
    if col.endswith("_answer"):
        model_name = col.replace("_answer", "")
        # Count nans and valid rows
        nan_count = balanced_df[col].isna().sum()
        valid_rows = balanced_df[balanced_df[col].notna()]
        accuracy = (valid_rows[col] == valid_rows["label_new"]).mean()
        print(f"{model_name}:")
        print(f"  Accuracy: {accuracy:.2%}")
        print(f"  Missing predictions: {nan_count}")

# Replace main df with balanced version
# balanced_df.to_csv("stance-eval-02.csv", index=False)


# %%

incorrect = df[df["ds_answer"] != df["label_new"]]
incorrect.to_csv("incorrect.csv", index=False)

# %%

# Filter for cases where the true label is not 'off-topic' (i.e. there is a stance)
has_stance = df[df["label_new"] != "off-topic"]

# Calculate accuracy on cases with stance
stance_accuracy = (has_stance["ds_answer"] == has_stance["label_new"]).mean()
print(f"\nAccuracy on posts with stance: {stance_accuracy:.2%}")

# Show confusion matrix for cases with stance
stance_confusion = pd.crosstab(
    has_stance["label_new"], has_stance["ds_answer"], margins=True
)
print("\nConfusion Matrix (posts with stance only):")
print(stance_confusion)

# Calculate direct favor/against misclassifications
# For each true label, calculate distribution of predictions
for true_label in df["label_new"].unique():
    total = len(df[df["label_new"] == true_label])
    predictions = df[df["label_new"] == true_label]["ds_answer"].value_counts()

    print(f"\nTrue label '{true_label}' ({total} posts):")
    for pred_label, count in predictions.items():
        percentage = count / total * 100
        print(f"- Predicted as '{pred_label}': {count} ({percentage:.1f}%)")

# Analyze confidence levels for incorrect predictions
incorrect_conf = df[df["ds_answer"] != df["label_new"]]["ds_confidence"].value_counts()
total_incorrect = len(df[df["ds_answer"] != df["label_new"]])

print("\nConfidence levels for incorrect predictions:")
for conf_level, count in incorrect_conf.items():
    percentage = count / total_incorrect * 100
    print(f"- {conf_level}: {count} ({percentage:.1f}%)")

# Calculate specific none/off-topic confusion
none_offtopic = df[
    ((df["label_new"] == "none") & (df["ds_answer"] == "off-topic"))
    | ((df["label_new"] == "off-topic") & (df["ds_answer"] == "none"))
]

print("\nNone vs Off-topic confusion:")
print(f"Total none/off-topic confusions: {len(none_offtopic)}")

# Break down by specific misclassification type
none_as_offtopic = len(
    df[(df["label_new"] == "none") & (df["ds_answer"] == "off-topic")]
)
offtopic_as_none = len(
    df[(df["label_new"] == "off-topic") & (df["ds_answer"] == "none")]
)

print(f"'none' predicted as 'off-topic': {none_as_offtopic}")
print(f"'off-topic' predicted as 'none': {offtopic_as_none}")


# %% Accuracy vs Latency Plot

MODELS = [
    "DeepSeek-R1",
    "R1-Dist-Llama-70B",
    "R1-Dist-Qwen-14B",
    "R1-Dist-Qwen-1.5B",
    "GPT-4o-mini",
    "4o-mini-3-shot",
]

ACCURACIES = [0.77, 0.73, 0.50, 0.21, 0.72, 0.74]  # Accuracy scores
latencies = [33.6, 10.4, 3.2, 1.5, 3.2, 3.2]  # Latency in ms

# Create DataFrame
df = pd.DataFrame({"Model": MODELS, "Latency": latencies, "Accuracy": ACCURACIES})

# Set style
sns.set_context("talk")
sns.set_style("white")

# Create scatter plot
plt.figure(figsize=(12, 8))
g = sns.scatterplot(data=df, x="Latency", y="Accuracy", s=200, color="#1f77b4")

font_size = 25

# Add labels for each point
for idx, row in df.iterrows():
    # Adjust offsets based on model to prevent overlap
    if row["Model"] == "DeepSeek-R1":
        offset = (10, -20)
    elif row["Model"] == "GPT-4o-mini":
        offset = (-30, -40)
    else:  # DeepSeek-R1-Distill-Qwen-1.5B
        offset = (10, 10)

    g.annotate(
        row["Model"],
        (row["Latency"], row["Accuracy"]),
        xytext=offset,
        textcoords="offset points",
        fontsize=font_size,
    )

# Customize the plot
plt.xlabel("Avg. Classification Time (s)", fontsize=font_size)
plt.ylabel("Accuracy", fontsize=font_size)
plt.title("Model Accuracy vs. Computational Cost", pad=20, fontsize=font_size * 1.1)
# Increase axis label font size and line widths
plt.xticks(fontsize=font_size)
plt.yticks(fontsize=font_size)
plt.gca().spines["left"].set_linewidth(3)
plt.gca().spines["bottom"].set_linewidth(3)

sns.despine()
plt.tight_layout()

plt.savefig("../img/llm-accuracy-vs-cost.png", dpi=300)

plt.show()


# %% Accuracy vs Cost Plot


# Example data (to be replaced with real values)
costs = [400, 160, 128, 14.4, 30]  # Cost per inference in USD

# Create DataFrame
df = pd.DataFrame({"Model": MODELS, "Cost": costs, "Accuracy": ACCURACIES})

# Set style
sns.set_context("talk")
sns.set_style("white")

# Create scatter plot
plt.figure(figsize=(12, 8))
g = sns.scatterplot(data=df, x="Cost", y="Accuracy", s=200, color="#1f77b4")

font_size = 25

# Add labels for each point
for idx, row in df.iterrows():
    # Adjust offsets based on model to prevent overlap
    if row["Model"] == "DeepSeek-R1":
        offset = (10, -20)
    elif row["Model"] == "GPT-4o-mini":
        offset = (-30, -40)
    else:  # DeepSeek-R1-Distill-Qwen-1.5B
        offset = (10, 10)

    g.annotate(
        row["Model"],
        (row["Cost"], row["Accuracy"]),
        xytext=offset,
        textcoords="offset points",
        fontsize=font_size,
    )

# Customize the plot
plt.xlabel("Cost per 100K Posts (USD)", fontsize=font_size)
plt.ylabel("Accuracy", fontsize=font_size)
plt.title("Model Accuracy vs. Financial Cost", pad=20, fontsize=font_size * 1.1)

# Increase axis label font size and line widths
plt.xticks(fontsize=font_size)
plt.yticks(fontsize=font_size)
plt.gca().spines["left"].set_linewidth(3)
plt.gca().spines["bottom"].set_linewidth(3)

sns.despine()
plt.tight_layout()

plt.savefig("../img/llm-accuracy-vs-financial-cost.png", dpi=300)

plt.show()


# %%

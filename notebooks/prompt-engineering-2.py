# %% Imports

import os
import typing as t
from collections import Counter
from enum import Enum

from openai import OpenAI
from pydantic import BaseModel

from bsky_net import Post, jsonl

# Constants
EXPERIMENTS_DIR = "../data/experiments"
TEST_SET_PATH = f"{EXPERIMENTS_DIR}/test-set-v1-sanitized.jsonl"

START_DATE = "2023-05-25"
END_DATE = "2023-05-26"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# %% Prompt helpers

MODEL = "gpt-4o-mini"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

    # sentiment: Sentiment


class UserPrompts:
    v7: str = """{context}
{text}

Which of the following describes the stance of the above post?
A: {stance}
B: {stance}

"""


def make_prompt(post: Post):
    return f"""Classify the following:
Text: "{post["text"]}"
Class:"""


# %% Structured output testing

Stance = t.Literal["favor", "against", "none", "unrelated"]


class Topic(str, Enum):
    moderation_policies = (
        "Discussing Bluesky's official rules or policies on content moderation"
    )
    content_removal = "About content being removed or flagged by Bluesky"
    account_removal = (
        "About Bluesky users being suspended or banned, including reasons and appeals"
    )
    trust_and_safety = (
        "Discussions on Bluesky's user safety, harassment, or harmful content"
    )
    transparency = "Expressing concerns or praises about the transparency of Bluesky's moderation decisions"
    algorithmic_moderation = (
        "About AI-based or automated moderation systems used by Bluesky"
    )
    community_moderation = "Discussions about user-driven moderation on Bluesky, like flagging or reporting content"
    moderation_criticism = "Criticizing Bluesky's moderation efforts (e.g., over-enforcement or under-enforcement)"
    moderation_praise = "Commending Bluesky's moderation efforts or improvements"
    general_moderation = (
        "Broad posts about Bluesky's moderation without a specific focus"
    )
    unrelated = "Posts that are not discussing Bluesky's moderation efforts at all."


# Structured output
class StanceDetection(BaseModel):
    # topic: list[Topic]
    stance: Stance
    reasoning: str


SEMEVAL_TRIAL_PATH = "../data/experiments/test-sets/semeval-trial.jsonl"

SemEvalSample = t.TypedDict(
    "SemEvalSample",
    {
        "ID": str,
        "Target": str,
        "post": str,
        "Stance": t.Literal["FAVOR", "AGAINST", "NONE"],
        "Opinion towards": t.Literal["TARGET", "OTHER", "NO_ONE"],
        "Sentiment": t.Literal["POSITIVE", "NEGATIVE", "NEUTRAL"],
    },
)

BSKY_TEST_PATH = "../data/experiments/test-sets/moderation-v1-sanitized.jsonl"


class BskySample(Post):
    classification: t.Literal[0, 1]


results = Counter()

sys_prompt = """Q: What is the Bluesky post's stance on the target? If the post is not clearly referencing the target, choose 'unrelated' and explain why.
The options are:
- against
- favor
- none
- unrelated

post: <I'm sick of celebrities who think being a well known actor makes them an authority on anything else. #robertredford #UN>
target: Liberal Values
reasoning: the author is implying that celebrities should not be seen as authorities on political issues, which is often associated with liberal values such as Robert Redford who is a climate change activist -> the author is against liberal values
stance: against

post: <I believe in a world where people are free to move and choose where they want to live>
target: Immigration
reasoning: the author is expressing a belief in a world with more freedom of movement -> the author is in favor of immigration
stance: favor

post: <I love the way the sun sets every day. #Nature #Beauty>
target: Conservative Party
reasoning: the author is in favor of nature and beauty -> the author is neutral towards taxes
stance: unrelated

post: <If a woman chooses to pursue a career instead of staying at home, is she any less of a mother?>
target: Conservative Party
reasoning: the author is questioning traditional gender roles, which are often supported by the conservative party -> the author is against the conservative party
stance: against

post: <We need to make sure that mentally unstable people can't become killers #protect #US>
target: Gun Control
reasoning: the author is advocating for measures to prevent mentally unstable people from accessing guns -> the author is in favor of gun control
stance: favor

post: <There is no shortcut to success, there's only hard work and dedication #Success #SuccessMantra>
target: Open Borders
reasoning: the author is in favor of hard work and dedication -> the author is neutral towards open borders
stance: none
"""

user_prompt = """post: <{text}>
target: {target}
"""


class Evidence(BaseModel):
    phrase: str
    reasoning: str


class StanceReasoning(BaseModel):
    evidence: list[Evidence]
    final_answer: t.Literal["favor", "against", "none", "unrelated"]


TARGET = "Bluesky's moderation efforts"

# for sample in jsonl[SemEvalSample].iter(SEMEVAL_TRIAL_PATH):
for sample in jsonl[BskySample].iter(BSKY_TEST_PATH):
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """You are an NLP expert, tasked with annotating posts from the social network Bluesky to determine the post's stance on Bluesky's moderation policies, trust and safety, and user removal, especially in relation to the Bluesky development team. If the post is not CLEARLY referencing the BLUESKY PLATFORM ITSELF and ITS moderation policies, classify it's stance as 'unrelated'. Otherwise, classify the stance of the post as 'favor', 'against', or 'none'.

Since you're an expert, you're able to understand sarcasm, irony, and other forms of figurative language. You're also able to understand the nuance in the post's stance and reference to the Bluesky platform or development team.
""",
            },
            {
                "role": "user",
                "content": sample["text"],
            },
        ],
        temperature=0.0,
        response_format=StanceReasoning,
    )

    stance = completion.choices[0].message.parsed

    if not stance:
        continue

    # print(stance.model_dump())
    print("TEXT: ", sample["text"])

    # if (
    #     stance.topic != sample["Target"].lower()
    #     and sample["Opinion towards"] == "TARGET"
    # ):
    #     print("Topic mismatch", stance.topic, sample["Target"])

    # elif stance.stance != sample["Stance"].lower():
    #     print("Stance mismatch", stance.stance, sample["Stance"])

    # else:
    #     print("Match!")

    # if Topic.unrelated in stance.topic and sample["classification"] == 1:
    #     print("FALSE NEGATIVE")
    #     results["fn"] += 1

    # elif Topic.unrelated not in stance.topic and sample["classification"] == 0:
    #     print("FALSE POSITIVE")
    #     results["fp"] += 1

    # elif Topic.unrelated in stance.topic and sample["classification"] == 0:
    #     print("TRUE NEGATIVE")
    #     results["tn"] += 1

    # elif Topic.unrelated not in stance.topic and sample["classification"] == 1:
    #     print("TRUE POSITIVE")
    #     results["tp"] += 1

    if stance.final_answer == "unrelated" and sample["classification"] == 1:
        print("FALSE NEGATIVE")
        results["fn"] += 1

    elif stance.final_answer != "unrelated" and sample["classification"] == 0:
        print("FALSE POSITIVE")
        results["fp"] += 1

    elif stance.final_answer == "unrelated" and sample["classification"] == 0:
        print("TRUE NEGATIVE")
        results["tn"] += 1

    elif stance.final_answer != "unrelated" and sample["classification"] == 1:
        print("TRUE POSITIVE")
        results["tp"] += 1

    # print("TOPICS: ", [topic.name for topic in stance.topic])
    print("STANCE: ", stance.final_answer)
    print("REASONING: ", stance.evidence)
    print()

tp = results["tp"]
tn = results["tn"]
fp = results["fp"]
fn = results["fn"]
total = tp + tn + fp + fn

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1_score = (
    2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
)
accuracy = (tp + tn) / total if total > 0 else 0

print(
    f"TP: {tp:<2} ({tp/total:.2%}) | FP: {fp:<2} ({fp/total:.2%})\n"
    f"FN: {fn:<2} ({fn/total:.2%}) | TN: {tn:<2} ({tn/total:.2%})\n\n"
    f"Precision: {precision:.4f}\n"
    f"Recall:    {recall:.4f}\n"
    f"F1 Score:  {f1_score:.4f}\n"
    f"Accuracy:  {accuracy:.4f}\n"
    f"{'=' * 20}"
)

# %%

"""
System prompt v1: Determine the topic of the user's Bluesky post and their stance on it.

Precision: 0.7528
Recall:    0.9437
F1 Score:  0.8375
Accuracy:  0.7679

-------------------

System prompt v2: You are tasked with classifying posts from the social network Bluesky to determine if they reference the network's moderation policies, especially in relation to the Bluesky development team. Each post may belong to one or more categories, but if they aren't clearly referencing the Bluesky platform and its moderation policies, classify it as 'Unrelated.' In addition, for each category, determine the stance of the post with respect to those topics.

TP: 60 (53.57%) | FP: 6  (5.36%)
FN: 11 (9.82%) | TN: 35 (31.25%)

Precision: 0.9091
Recall:    0.8451
F1 Score:  0.8759
Accuracy:  0.8482

-------------------

System prompt v2 with fixing Bluesky general moderation:

Precision: 0.8824
Recall:    0.8451
F1 Score:  0.8633
Accuracy:  0.8304

-------------------

System prompt v3: You are an NLP expert, tasked with annotating posts from the social network Bluesky to determine if they reference the network's moderation policies, especially in relation to the Bluesky development team. Each post may belong to one or more categories, but if they aren't CLEARLY referencing the BLUESKY PLATFORM ITSELF and ITS moderation policies, classify it as 'Unrelated.' In addition, for each category, determine the stance of the post with respect to those topics.

Precision: 0.9375
Recall:    0.8451
F1 Score:  0.8889
Accuracy:  0.8661

v3 with clearer stance description: You are an NLP expert, tasked with annotating posts from the social network Bluesky to determine if they reference the network's moderation policies, especially in relation to the Bluesky development team. Each post may belong to one or more categories, but if they aren't CLEARLY referencing the BLUESKY PLATFORM ITSELF and ITS moderation policies, classify it as 'Unrelated.' In addition, determine the STANCE of the USER on BLUESKY'S moderation performance.


v4: Q: What is the post's stance on the target?
The options are:
- against
- favor
- none

post: <I'm sick of celebrities who think being a well known actor makes them an authority on anything else. #robertredford #UN>
target: Liberal Values
reasoning: the author is implying that celebrities should not be seen as authorities on political issues, which is often associated with liberal values such as Robert Redford who is a climate change activist -> the author is against liberal values
stance: against

post: <I believe in a world where people are free to move and choose where they want to live>
target: Immigration
reasoning: the author is expressing a belief in a world with more freedom of movement -> the author is in favor of immigration
stance: favor

post: <I love the way the sun sets every day. #Nature #Beauty>
target: Taxes
reasoning: the author is in favor of nature and beauty -> the author is neutral towards taxes
stance: none

post: <If a woman chooses to pursue a career instead of staying at home, is she any less of a mother?>
target: Conservative Party
reasoning: the author is questioning traditional gender roles, which are often supported by the conservative party -> the author is against the conservative party
stance: against

post: <We need to make sure that mentally unstable people can't become killers #protect #US>
target: Gun Control
reasoning: the author is advocating for measures to prevent mentally unstable people from accessing guns -> the author is in favor of gun control
stance: favor

post: <There is no shortcut to success, there's only hard work and dedication #Success #SuccessMantra>
target: Open Borders
reasoning: the author is in favor of hard work and dedication -> the author is neutral towards open borders
stance: none

post: <{text}>
target: {target}
reasoning:

CoT:

Precision: 0.9661
Recall:    0.8028
F1 Score:  0.8769
Accuracy:  0.8571

CoT with extra sentence:


TODO: Stance labels
"""

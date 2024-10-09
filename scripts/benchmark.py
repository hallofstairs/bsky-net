# %% Imports

import json
import os
import typing as t
from collections import Counter

from openai import OpenAI
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel

from bsky_net import jsonl

BENCHMARK_PATH = "./data/experiments/test-sets/moderation-topic-stance.jsonl"
MODEL = "gpt-4o-mini"

# TODO: Ask to determine if it's a genuine opinion or humourous

SYSTEM_PROMPT = """You are an NLP expert, tasked with performing opinion mining on posts from the Bluesky social network. Your goal is to detect the post author's opinion on the Bluesky team's approach thus far to moderation and trust and safety (T&S) on their platform. 

If the post is unrelated to moderation on Bluesky, indicate that the post is 'off-topic'.

Include quotes from the text that you used to reach your answer."""


TOPIC_STANCE_SCHEMA: JSONSchema = {
    "name": "opinion_mining",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["reasoning", "on_topic"],
        "additionalProperties": False,
        "properties": {
            "reasoning": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["quote", "conclusion"],
                    "properties": {
                        "quote": {"type": "string"},
                        "conclusion": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "on_topic": {"type": "boolean"},
        },
    },
}

print(json.dumps(TOPIC_STANCE_SCHEMA, indent=2))

ConfusionVal = t.Literal["tp", "fp", "tn", "fn"]


class StanceEval(t.TypedDict):
    favor: ConfusionVal
    against: ConfusionVal
    none: ConfusionVal


class Result(t.TypedDict):
    topic: ConfusionVal
    stance: t.Optional[StanceEval]


def evaluate(pred: "StanceClassification", true: "TopicStanceSample") -> Result:
    def confusion_val(stance: Stance) -> ConfusionVal:
        if true.stance == stance:
            if pred.opinion == stance:
                return "tp"
            else:
                return "fn"
        else:
            if pred.opinion == stance:
                return "fp"
            else:
                return "tn"

    if pred.on_topic:
        if not true.on_topic:
            return {"topic": "fp", "stance": None}

        stance_eval: StanceEval = {
            "favor": confusion_val("favor"),
            "against": confusion_val("against"),
            "none": confusion_val("none"),
        }

        return {"topic": "tp", "stance": stance_eval}

    elif not pred.on_topic:
        if true.on_topic:
            return {"topic": "fn", "stance": None}

        return {"topic": "tn", "stance": None}

    raise ValueError("Unknown case")


def confusion_mat(title: str, results: Counter) -> None:
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
        f"{title}\n"
        f"TP: {tp:<2} ({tp/total:.2%}) | FP: {fp:<2} ({fp/total:.2%})\n"
        f"FN: {fn:<2} ({fn/total:.2%}) | TN: {tn:<2} ({tn/total:.2%})\n\n"
        f"Precision: {precision:.4f}\n"
        f"Recall:    {recall:.4f}\n"
        f"F1 Score:  {f1_score:.4f}\n"
        f"Accuracy:  {accuracy:.4f}\n"
        f"{'=' * 20}"
    )


Stance = t.Literal["favor", "against", "none"]


class TopicStanceSample(BaseModel):
    text: str
    on_topic: bool
    stance: t.Optional[Stance] = None
    bsky_team: t.Optional[t.Literal[True]] = None


class Reasoning(BaseModel):
    quote: str
    conclusion: str


class StanceClassification(BaseModel):
    on_topic: bool
    opinion: t.Optional[Stance] = None
    reasoning: list[Reasoning]
    # main_topic: str
    # is_satirical: bool
    # conclusion: str


print("MODEL:", MODEL)
print("SYSTEM PROMPT:")
print(SYSTEM_PROMPT)
print("=" * 40)

topic_eval = Counter()
stance_eval: dict[Stance, Counter[ConfusionVal]] = {
    "favor": Counter(),
    "against": Counter(),
    "none": Counter(),
}

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


for obj in jsonl[dict].iter(BENCHMARK_PATH):
    sample = TopicStanceSample.model_validate(obj)

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sample.text},
        ],
        temperature=0.0,
        response_format={"type": "json_schema", "json_schema": TOPIC_STANCE_SCHEMA},
    )

    if not completion.choices[0].message.content:
        raise ValueError("No content in completion")

    pred = StanceClassification.model_validate(
        json.loads(completion.choices[0].message.content)
    )

    if not pred:
        print("NO PREDICTION")
        print(completion.choices[0])
        continue

    result = evaluate(pred, sample)

    topic_eval[result["topic"]] += 1
    if result["stance"]:
        stance_eval["favor"][result["stance"]["favor"]] += 1
        stance_eval["against"][result["stance"]["against"]] += 1
        stance_eval["none"][result["stance"]["none"]] += 1

    if sample.on_topic != pred.on_topic:
        print("TEXT: ")
        print(sample.text, "\n")
        print(f"Pred - {'on-topic' if pred.on_topic else 'off-topic'}, {pred.opinion}")
        print(
            f"True - {'on-topic' if sample.on_topic else 'off-topic'}, {sample.stance}"
        )
        # print(f"Conclusion: {pred.conclusion}")
        print("Reasoning:")
        for reason in pred.reasoning:
            print(f"  - Quote: {reason.quote}")
            print(f"  - Conclusion: {reason.conclusion}")
            print()
        print("-" * 40)
        continue

    # if sample.stance and sample.stance != pred.opinion:
    #     print("TEXT: ")
    #     print(sample.text, "\n")
    #     print(f"Pred - {'on-topic' if pred.on_topic else 'off-topic'}, {pred.opinion}")
    #     print(
    #         f"True - {'on-topic' if sample.on_topic else 'off-topic'}, {sample.stance}"
    #     )
    #     # print(f"Conclusion: {pred.conclusion}")
    #     print("Reasoning:")
    #     for reason in pred.reasoning:
    #         print(f"  - Quote: {reason.quote}")
    #         print(f"  - Conclusion: {reason.conclusion}")
    #         print()
    #     print("-" * 40)
    #     continue

stance_combined = stance_eval["favor"] + stance_eval["against"] + stance_eval["none"]

confusion_mat("TOPIC", topic_eval)
confusion_mat("STANCE", stance_combined)

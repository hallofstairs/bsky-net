import json
import os
import typing as t

from pydantic import BaseModel, ValidationError

from bsky_net import jsonl

BATCH_DESCRIPTION = "en-moderation-topic-stance-2023-05-28-V2"

BATCH_OUTPUT_DIR = f"data/batches/{BATCH_DESCRIPTION}/out"


class Reasoning(BaseModel):
    quote: str
    conclusion: str


class StanceClassification(BaseModel):
    on_topic: bool
    opinion: t.Literal["favor", "against", "none"]
    reasoning: list[Reasoning]


on_topic_uris: dict[str, t.Literal["favor", "against", "none"]] = {}
count = 0

for file in sorted(os.listdir(BATCH_OUTPUT_DIR)):
    path = f"{BATCH_OUTPUT_DIR}/{file}"

    for obj in jsonl[dict].iter(path):
        try:
            res = StanceClassification.model_validate_json(
                obj["response"]["body"]["choices"][0]["message"]["content"]
            )
        except ValidationError:
            print(f"Validation error for {obj['custom_id']}")
            continue

        if res.on_topic:
            on_topic_uris[obj["custom_id"]] = res.opinion

        count += 1

print(
    f"{count} total posts, {len(on_topic_uris)} on-topic ({len(on_topic_uris) / count * 100:.2f}%)"
)

OUTPUT_FILE = f"data/processed/{BATCH_DESCRIPTION}-zipped.json"

with open(OUTPUT_FILE, "w") as f:
    json.dump(on_topic_uris, f, indent=4)

print(f"On-topic URIs and opinions have been written to {OUTPUT_FILE}")

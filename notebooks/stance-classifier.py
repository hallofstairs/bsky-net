# %% Imports

import json
import os
import typing as t
from collections import defaultdict
from itertools import count

import langid
from openai import OpenAI
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel, ValidationError

from bsky_net import Post, did_from_uri, jsonl, records

# TODO: Double check all of this
# TODO: Combine all `out` files into a single file?


# Constants
BATCH_DIR = "../data/batches/cot-moderation-2023-05-24_2023-05-28"
STREAM_DIR = "../data/raw/en-stream-2023-07-01"

# %% Helpers


class ReplyUris(BaseModel):
    root: str
    parent: str


def get_reply_uris(post: Post) -> ReplyUris:
    if "reply" not in post or not post["reply"]:
        raise ValueError("Post is not a reply")
    return ReplyUris(
        root=post["reply"]["root"]["uri"], parent=post["reply"]["parent"]["uri"]
    )


def get_subject_uri(post: Post) -> t.Optional[str]:
    if "embed" not in post or not post["embed"]:
        raise ValueError("Post is not a quote")

    try:
        if post["embed"]["$type"] == "app.bsky.embed.record":
            return post["embed"]["record"]["uri"]
        elif post["embed"]["$type"] == "app.bsky.embed.recordWithMedia":
            return post["embed"]["record"]["record"]["uri"]
    except KeyError:
        return None


def is_english(text: str) -> bool:
    return langid.classify(text)[0] == "en"


# %% Load in all root on-topic posts

# Whole process:
# Pre-batch: filter for English posts
# Run batch classification for being on-topic
# Gather all posts related to on-topic posts (quotes, replies)
# Run stance classification for all related posts

# This process:
# 1. Load in all on-topic posts from batch
# 2.
# Need: list of all on-topic English posts and their quotes/replies


class Reasoning(BaseModel):
    quote: str
    conclusion: str


class StanceClassification(BaseModel):
    on_topic: bool
    reasoning: list[Reasoning]


on_topic_uris: set[str] = set()
total_posts = 0

for file in sorted(os.listdir(f"{BATCH_DIR}/out")):
    path = f"{BATCH_DIR}/out/{file}"

    for obj in jsonl[dict].iter(path):
        try:
            res = StanceClassification.model_validate_json(
                obj["response"]["body"]["choices"][0]["message"]["content"]
            )
        except ValidationError:
            continue

        if res.on_topic:
            on_topic_uris.add(obj["custom_id"])

        total_posts += 1

print(
    f"{total_posts} total posts, {len(on_topic_uris)} on-topic ({len(on_topic_uris) / total_posts * 100:.2f}%)"
)

# %% Filter for on-topic English posts

on_topic_en_uris: set[str] = set()

for record in records(STREAM_DIR, start_date="2023-05-24", end_date="2023-05-28"):
    if record["$type"] != "app.bsky.feed.post":
        continue

    if record["uri"] in on_topic_uris and is_english(record["text"]):
        on_topic_en_uris.add(record["uri"])

print(
    f"{len(on_topic_en_uris)} on-topic English posts ({len(on_topic_en_uris) / len(on_topic_uris) * 100:.2f}%)"
)

# %% Get all posts related to on-topic posts (quotes, replies)


class OGNode(BaseModel):
    node_id: int
    did: str
    uri: str
    text: str


class QuoteNode(BaseModel):
    node_id: int
    did: str
    uri: str
    text: str
    subject_uri: str


class ReplyNode(BaseModel):
    node_id: int
    did: str
    uri: str
    text: str
    root_uri: str
    parent_uri: str


# TODO: Some posts are both replies and quotes
Node = OGNode | QuoteNode | ReplyNode
on_topic_posts: dict[str, Node] = {}

did_idx = count()
did_enums = defaultdict(lambda: next(did_idx))


# Create post ref
for record in records(STREAM_DIR, start_date="2023-05-24", end_date="2023-05-28"):
    if record["$type"] != "app.bsky.feed.post":
        continue

    post = record

    # Assign replies label of root
    if "reply" in post and post["reply"]:
        reply_uris = get_reply_uris(post)

        if reply_uris.root in on_topic_en_uris and is_english(post["text"]):
            on_topic_posts[post["uri"]] = ReplyNode(
                node_id=did_enums[post["did"]],
                did=post["did"],
                uri=post["uri"],
                text=post["text"],
                root_uri=reply_uris.root,
                parent_uri=reply_uris.parent,
            )
            continue

    # Assign quotes label of subject
    if "embed" in post and post["embed"]:
        subject_uri = get_subject_uri(post)

        if not subject_uri:  # Not a quote post
            continue

        if subject_uri in on_topic_en_uris and is_english(post["text"]):
            on_topic_posts[post["uri"]] = QuoteNode(
                node_id=did_enums[post["did"]],
                did=post["did"],
                uri=post["uri"],
                text=post["text"],
                subject_uri=subject_uri,
            )
            continue

    if post["uri"] in on_topic_en_uris and is_english(post["text"]):
        on_topic_posts[post["uri"]] = OGNode(
            node_id=did_enums[post["did"]],
            did=post["did"],
            uri=post["uri"],
            text=post["text"],
        )


# %% Assemble prompts with parent context


def get_parent_ctx(node: Node, ref: dict[str, Node]) -> str:
    if type(node) is QuoteNode:  # this post is a quote of parent
        prev_uri = node.subject_uri
    if type(node) is ReplyNode:  # this post is a reply to parent
        # print("has reply parent")
        prev_uri = node.parent_uri
    if type(node) is OGNode:  # this post is the root, has no parent
        # print("has no parent")
        return ""

    if prev_uri not in ref:  # parent was deleted
        parent_did = did_from_uri(prev_uri)

        if type(node) is ReplyNode:
            root = ref[node.root_uri]
            return (
                f"User {root.node_id}: `{root.text}`\n"
                + f"User {did_enums[parent_did]}: <post deleted by author>\n"
            )
        if type(node) is QuoteNode:
            return f"User {did_enums[parent_did]}: <post deleted by author>\n"

    parent = ref[prev_uri]

    if type(parent) is OGNode:
        return f"User {parent.node_id}: `{parent.text}`\n"
    if type(parent) is ReplyNode:
        # print("parent is a reply to another parent, recursing")
        return get_parent_ctx(parent, ref) + f"User {parent.node_id}: `{parent.text}`\n"
    if type(parent) is QuoteNode:
        # print("parent is a quote of another parent, recursing")
        return get_parent_ctx(parent, ref) + f"User {parent.node_id}: `{parent.text}`\n"

    raise ValueError("Unfamiliar type")


user_prompts = []

for uri, node in on_topic_posts.items():
    if type(node) is not OGNode:  # Needs context of parent(s)
        context = get_parent_ctx(node, on_topic_posts)
        user_prompt: str = (
            f"<context>\n{context}</context>\n\n" f"User {node.node_id}: `{node.text}`"
        )
    else:
        user_prompt = node.text

    # print(user_prompt)
    # print("-" * 5)

    user_prompts.append(user_prompt)

# %% Prompting

# TODO: Would it help if I said "User X's" opinion instead of "author's"?
# TODO: try the 10-pretty-good prompt

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = """You are an NLP expert, tasked with performing stance detection on posts from the Bluesky social network. Your goal is to detect the post author's stance on the Bluesky team's approach to moderation and trust and safety (T&S) on their platform.

If the post is unrelated to social media moderation on Bluesky specifically, indicate that the post is 'off-topic'.

If the post is on-topic, classify the stance of the author on the BLUESKY TEAM's MODERATION EFFORTS as defending/sympathizing with them (favor), criticizing them (against), or neither (none). If the post's opinion is not directed towards the BLUESKY TEAM's moderation approach, even if it's on-topic, indicate that the opinion is 'none'.

Include quotes from the text that you used to reach your answer."""


TOPIC_STANCE_SCHEMA: JSONSchema = {
    "name": "stance_detection",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["reasoning", "on_topic", "opinion"],
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
            "opinion": {"enum": ["favor", "against", "none"], "type": "string"},
        },
    },
}


class StancePrediction(BaseModel):
    reasoning: list[Reasoning]
    on_topic: bool
    opinion: t.Literal["favor", "against", "none"]


for user_prompt in user_prompts:
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_schema", "json_schema": TOPIC_STANCE_SCHEMA},
    )

    if not completion.choices[0].message.content:
        raise ValueError("No content in completion")

    pred = StancePrediction.model_validate(
        json.loads(completion.choices[0].message.content)
    )

    print(f"Prompt: {user_prompt}")
    print(pred.model_dump_json(indent=2))
    print("-" * 5)

    with open("../evals/moderation/stance-detection.jsonl", "a") as f:
        obj = {
            "text": user_prompt,
            "on_topic": pred.on_topic,
            "opinion": pred.opinion,
        }
        f.write(json.dumps(obj) + "\n")

# %% User-based stance classification

USER_DID = "did:plc:xgjcudwc5yk4z2uex5v6e7bl"

user_posts = [
    post
    for post in on_topic_posts.values()
    if type(post) is OGNode and post.did == USER_DID
][:5]

full_user_prompt = "\n".join(
    [f"post_{i}: `{post.text}`" for i, post in enumerate(user_posts)]
)

# %%

SYSTEM_PROMPT = """You are an NLP expert, tasked with performing stance detection on a Bluesky user's posts. Your goal is to detect the user's stance on the Bluesky team's approach to moderation and trust and safety (T&S) on their platform.

For each post, you will:
1. Determine if the post is related to social media moderation efforts on Bluesky specifically
2. Classify the stance of the user towards the BLUESKY TEAM's MODERATION EFFORTS as defending/sympathizing with them (favor), criticizing them (against), or neither (none).

If the post is unrelated to social media moderation on Bluesky specifically, indicate that the post is 'off-topic'.

Include quotes from the text that you used to reach your answer."""


USER_STANCE_SCHEMA: JSONSchema = {
    "name": "stance_detection",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["posts"],
        "additionalProperties": False,
        "properties": {
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["post_id", "reasoning", "on_topic", "opinion"],
                    "additionalProperties": False,
                    "properties": {
                        "post_id": {"type": "string"},
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
                        "opinion": {
                            "enum": ["favor", "against", "none"],
                            "type": "string",
                        },
                    },
                },
            },
        },
    },
}

completion = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_user_prompt},
    ],
    temperature=0.0,
    response_format={"type": "json_schema", "json_schema": USER_STANCE_SCHEMA},
)

if not completion.choices[0].message.content:
    raise ValueError("No content in completion")

pred = StancePrediction.model_validate(
    json.loads(completion.choices[0].message.content)
)

print(f"Prompt: {full_user_prompt}")
print(pred.model_dump_json(indent=2))
print("-" * 5)

# %%

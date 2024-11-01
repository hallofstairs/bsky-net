# Using the output from topic classification, run stance detection

# %%
import json
import os
import typing as t
from collections import defaultdict
from itertools import count

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel, ValidationError

from bsky_net import Post, did_from_uri, jsonl, records

load_dotenv()

# Constants
BATCH_DIR = "../data/batches/cot-moderation-2023-05-24_2023-05-28"
STREAM_DIR = "../data/raw/stream-2023-07-01"
LOCAL_DIR = "../data/batches"

BATCH_DESCRIPTION = "cot-moderation-stance-2023-05-24_2023-05-28"

MODEL = "gpt-4o-mini"
BATCH_MAX_N = 49_900
BATCH_QUEUE_MAX_TOKENS = 19_000_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 237
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

# %%


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


class Reasoning(BaseModel):
    quote: str
    conclusion: str


class StanceClassification(BaseModel):
    on_topic: bool
    reasoning: list[Reasoning]


# Load in all root on-topic posts

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

# Filter for on-topic English posts

on_topic_en_uris: set[str] = set()

for record in records(STREAM_DIR, start_date="2023-05-24", end_date="2023-05-28"):
    if record["$type"] != "app.bsky.feed.post":
        continue

    if record["uri"] in on_topic_uris:
        on_topic_en_uris.add(record["uri"])

print(
    f"{len(on_topic_en_uris)} on-topic English posts ({len(on_topic_en_uris) / len(on_topic_uris) * 100:.2f}%)"
)

# Get all derivative on-topic posts (quotes, replies)


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

        if reply_uris.root in on_topic_en_uris:
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

        if subject_uri in on_topic_en_uris:
            on_topic_posts[post["uri"]] = QuoteNode(
                node_id=did_enums[post["did"]],
                did=post["did"],
                uri=post["uri"],
                text=post["text"],
                subject_uri=subject_uri,
            )
            continue

    if post["uri"] in on_topic_en_uris:
        on_topic_posts[post["uri"]] = OGNode(
            node_id=did_enums[post["did"]],
            did=post["did"],
            uri=post["uri"],
            text=post["text"],
        )


# Assemble prompts, including parent context for derivative posts


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


# %% Generate prompts

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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

if os.path.exists(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}"):
    raise ValueError(f"Batch folder '{BATCH_DESCRIPTION}' already exists.")

os.makedirs(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/in")
os.makedirs(f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/out")

i = 0
batch_size = 0
total_tokens = 0

for uri, node in on_topic_posts.items():
    if type(node) is not OGNode:  # Needs context of parent(s)
        context = get_parent_ctx(node, on_topic_posts)
        user_prompt: str = (
            f"<context>\n{context}</context>\n\n" f"User {node.node_id}: `{node.text}`"
        )
    else:
        user_prompt = node.text

    batch_obj = {
        "custom_id": uri,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {
                "type": "json_schema",
                "json_schema": TOPIC_STANCE_SCHEMA,
            },
        },
    }

    batch_path = f"{LOCAL_DIR}/{BATCH_DESCRIPTION}/in/{i}.jsonl"
    with open(batch_path, "a") as f:
        json.dump(batch_obj, f)
        f.write("\n")

    batch_size += 1
    total_tokens += AVG_TOKENS_PER_REQ

    if batch_size == BATCH_MAX_N or total_tokens > BATCH_QUEUE_MAX_TOKENS:
        # upload_file(batch_path)
        print(f"Batch {i} saved: {batch_size} posts, {total_tokens} tokens")
        i += 1
        batch_size = 0
        total_tokens = 0

    # print(user_prompt)
    # print("-" * 5)


# %% Generate batch files

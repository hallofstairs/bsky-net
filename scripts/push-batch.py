import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BATCH_DESCRIPTION = "en-moderation-topic-stance-2023-05-28-V2"
BATCH_IDX = sys.argv[1]

FILE_PATH = f"data/batches/{BATCH_DESCRIPTION}/in/{BATCH_IDX}.jsonl"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY_BLUESKY"))


def push_batch(path: str):
    """Upload a batch to the OpenAI Batch API."""

    batch_file = client.files.create(file=open(path, "rb"), purpose="batch")
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": f"{BATCH_DESCRIPTION}-{BATCH_IDX}"},
    )

    return batch


batch = push_batch(FILE_PATH)
print(f"Batch pushed. Batch ID: {batch.id}")

import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.batch import Batch

load_dotenv()

# Constants
BATCH_DIR = "data/batches"
BATCH_DESCRIPTION = "moderation-2023-05-24_2023-05-28"


def push_batch(path: str):
    """Upload a batch to the OpenAI Batch API."""

    batch_file = client.files.create(file=open(path, "rb"), purpose="batch")
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": f"{BATCH_DESCRIPTION}-{idx}"},
    )

    return batch


def batch_in_progress() -> tuple[Batch, int] | None:
    """Check if there are any batches in progress."""
    batches = client.batches.list().data
    for batch in batches:
        if (
            batch.status == "in_progress" or batch.status == "finalizing"
        ) and isinstance(batch.metadata, dict):
            return batch, int(batch.metadata.get("description", "")[-1])

    return None


idx = 0
batch: Batch | None = None

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Check on batches, push new one when done
while True:
    # Ready for next batch
    if not batch:
        next_batch_path = f"{BATCH_DIR}/{BATCH_DESCRIPTION}/in/{idx}.jsonl"

        if not os.path.exists(next_batch_path):
            print("No more batches to process. Exiting.")
            break

        if os.path.exists(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out/{idx}.jsonl"):
            print(f"Output file for batch {idx} already exists. Moving to next index.")
            idx += 1
            continue

        curr_batch = batch_in_progress()

        if curr_batch is not None:
            print(f"Batch {idx} already in progress. Waiting for completion...")
            batch, idx = curr_batch
            continue

        print(f"Pushing batch {idx}...")
        batch = push_batch(next_batch_path)
        print(f"Batch {idx} pushed. Batch ID: {batch.id}")

    batch_info = client.batches.retrieve(batch.id)

    # Batch failed
    if batch_info.failed_at:
        print(f"Batch {idx} failed. Error: {batch_info.errors}")
        batch = None
        idx += 1
        continue

    # Batch completed
    if batch_info.completed_at:
        if not batch_info.output_file_id:
            raise ValueError("Batch output file ID not found.")

        output = client.files.content(batch_info.output_file_id)

        with open(f"{BATCH_DIR}/{BATCH_DESCRIPTION}/out/{idx}.jsonl", "w") as f:
            f.write(output.text)

        print(f"Batch {idx} completed and results saved.")

        batch = None
        idx += 1

    print(
        f"[{time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())} UTC] Batch {idx} status: "
        f"{batch_info.request_counts.completed}/"  # type: ignore
        f"{batch_info.request_counts.total}"  # type: ignore
    )

    time.sleep(60)  # Ping Batch API every 60 seconds

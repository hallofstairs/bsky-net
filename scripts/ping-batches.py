import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Batch name
BATCH_DESCRIPTION = "en-moderation-topic-stance-2023-05-28-V2"

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
BATCH_DIR = SCRIPT_DIR.parent / "data" / "batches" / BATCH_DESCRIPTION

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class Batches:
    @classmethod
    def latest(cls) -> int:
        with open(BATCH_DIR / "batch.txt", "r") as file:
            return int(file.read(1))

    @classmethod
    def push(cls, idx: int) -> None:
        """Upload a batch to the OpenAI Batch API."""
        batch_file = client.files.create(
            file=open(BATCH_DIR / "in" / str(idx), "rb"), purpose="batch"
        )

        client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": f"{BATCH_DESCRIPTION}-{idx}"},
        )

        with open("batch.txt", "w") as file:
            file.write(str(idx))

    @classmethod
    def in_progress(cls) -> bool:
        """Check if there are any batches in progress."""
        return any(
            batch.status in {"in_progress", "finalizing"}
            for batch in client.batches.list().data
            if isinstance(batch.metadata, dict)
        )


if __name__ == "__main__":
    if Batches.in_progress():
        exit()

    next_batch_idx = Batches.latest() + 1
    Batches.push(next_batch_idx)
    exit()

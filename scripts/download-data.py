"""Download the bluesky dataset from Hugging Face."""

import os

from huggingface_hub import snapshot_download

HF_REPO_ID = "hallofstairs/bluesky"
TARGET_LOCAL_DIR = "data/raw/bluesky"

if __name__ == "__main__":
    os.makedirs(TARGET_LOCAL_DIR, exist_ok=True)
    print("Downloading bluesky dataset from Hugging Face...")

    snapshot_download(
        repo_id=HF_REPO_ID,
        repo_type="dataset",
        local_dir=TARGET_LOCAL_DIR,
        ignore_patterns=["README.md", ".gitattributes"],
    )

    print(f"Download complete. File saved to: {TARGET_LOCAL_DIR}")

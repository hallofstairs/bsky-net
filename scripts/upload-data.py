"""Upload the bluesky dataset to Hugging Face (only works if you have the credentials)"""

import os

from huggingface_hub import upload_folder

HF_REPO_ID = "hallofstairs/bluesky"
HF_TOKEN = os.getenv("HF_TOKEN")
TARGET_LOCAL_DIR = "data/raw/bluesky"

if __name__ == "__main__":
    print("Uploading bluesky dataset to Hugging Face...")

    upload_folder(
        repo_id=HF_REPO_ID,
        folder_path=TARGET_LOCAL_DIR,
        repo_type="dataset",
        token=HF_TOKEN,
    )

    print("Upload complete.")

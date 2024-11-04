"""Upload the bluesky dataset to Hugging Face (only works if you have the credentials)"""

from huggingface_hub import upload_large_folder

HF_REPO_ID = "hallofstairs/bsky-net"
TARGET_LOCAL_DIR = "data/processed/bsky-net-daily"

if __name__ == "__main__":
    print("Uploading bluesky dataset to Hugging Face...")

    upload_large_folder(
        repo_id=HF_REPO_ID,
        folder_path=TARGET_LOCAL_DIR,
        repo_type="dataset",
    )

    print("Upload complete.")

# Using the output from topic classification, run stance detection

import json
import os

from dotenv import load_dotenv

from bsky_net import Post, prompts, records

load_dotenv()

# Constants
STREAM_PATH = "data/raw/stream-2023-07-01"
LOCAL_DIR = "data/batches"
BUCKET_NAME = "main"
BUCKET_DIR = "bsky-net/batches"
BATCH_DESCRIPTION = "cot-moderation-2023-05-24_2023-05-28"

START_DATE = "2023-05-24"
END_DATE = "2023-05-28"

MODEL = "gpt-4o-mini"
BATCH_MAX_N = 49_900
BATCH_QUEUE_MAX_TOKENS = 19_000_000

AVG_TOKENS_PER_POST = 90
SYSTEM_PROMPT_TOKENS = 237
AVG_TOKENS_PER_REQ = SYSTEM_PROMPT_TOKENS + AVG_TOKENS_PER_POST

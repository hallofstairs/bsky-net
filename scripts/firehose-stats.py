import asyncio
import os
from datetime import datetime

import websockets
from dotenv import load_dotenv

load_dotenv()

# Get Bluesky service credentials from environment
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

# Stats tracking
start_time = None
record_count = 0


async def connect_firehose():
    """Connect to the Bluesky firehose websocket stream"""
    global start_time, record_count
    uri = "wss://jetstream2.us-east.bsky.network/subscribe"

    async with websockets.connect(uri) as websocket:
        print(f"Connected to firehose at {datetime.now()}")
        start_time = datetime.now()
        record_count = 0

        # Print initial stats display
        print("Records/sec: --.-")
        print("Total records: ----")
        print("Uptime: --.-s")
        print("---")
        # Move cursor back up 4 lines
        print("\033[F\033[F\033[F\033[F", end="")

        try:
            while True:
                message = await websocket.recv()
                try:
                    record_count += 1

                    # Update stats every second
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= 1:
                        records_per_sec = record_count / elapsed
                        # Clear lines and update
                        print(f"\rRecords/sec: {records_per_sec:.1f}    ")
                        print(f"\rTotal records: {record_count}    ")
                        print(f"\rUptime: {elapsed:.1f}s    ")
                        print("\r---    ")
                        # Move cursor back up
                        print("\033[F\033[F\033[F\033[F", end="")

                except UnicodeDecodeError:
                    print(f"Error: {message[:50]}... is not valid UTF-8")
                    continue

        except websockets.exceptions.ConnectionClosed:
            print("\n\nConnection closed, attempting to reconnect...")
        except Exception as e:
            print(f"\n\nError: {e}")


async def main():
    while True:
        try:
            await connect_firehose()
        except Exception as e:
            print(f"Connection failed: {e}")
            print("Retrying in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

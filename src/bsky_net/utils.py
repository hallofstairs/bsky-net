import sys
import time


def tq(iterable):
    total = len(iterable) if isinstance(iterable, list) else 31_000
    start_time = time.time()
    estimated_time_remaining = 0

    for i, item in enumerate(iterable):
        if i % (total / 100) == 0 or i == total - 1:
            elapsed_time = time.time() - start_time
            items_per_second = (i + 1) / elapsed_time if elapsed_time > 0 else 0
            estimated_time_remaining = (
                (total - i - 1) / items_per_second if items_per_second > 0 else 0
            )

        sys.stdout.write(
            f"\r{i+1}/{total} ({((i+1)/total)*100:.2f}%) - {estimated_time_remaining/60:.1f}m until done"
        )
        sys.stdout.flush()
        yield item
    sys.stdout.write("\n")


def did_from_uri(uri: str) -> str:
    return uri.split("/")[2]

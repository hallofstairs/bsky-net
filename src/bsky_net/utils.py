import json
import sys
import time
import typing as t

T = t.TypeVar("T")


class jsonl[T]:
    @classmethod
    def iter(cls, path: str) -> t.Generator[T, None, None]:
        with open(path, "r") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"JSONDecodeError: {line}")
                    continue


def tq(iterable: t.Iterable, active: bool = True) -> t.Generator[t.Any, None, None]:
    total = len(iterable) if isinstance(iterable, list) else 31_000  # lol
    start_time = time.time()
    estimated_time_remaining = 0

    for i, item in enumerate(iterable):
        if active:
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

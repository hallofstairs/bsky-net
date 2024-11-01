import os
import typing as t
from pathlib import Path

from bsky_net import TimeFormat, records

Opinion = t.Literal["favor", "against", "none"]


class RecordInfo(t.TypedDict):
    opinion: Opinion
    createdAt: str


class UserActivity(t.TypedDict):
    seen: dict[str, RecordInfo]
    liked: dict[str, RecordInfo]


BskyNetGraph: t.TypeAlias = dict[str, dict[str, UserActivity]]


class BskyNet:
    def __init__(
        self, window_size: TimeFormat, stream_dir: str, start_date: str, end_date: str
    ):
        self.window_size = window_size
        self.stream_dir = stream_dir
        self.start_date = start_date
        self.end_date = end_date

        self.data_path = self._data_path()

        self.bsky_net: t.Optional[BskyNetGraph] = None

        # TODO: Check built windows

    def build(self):
        if not os.path.exists(f"{self.data_path}/bsky-net/raw"):
            raise ValueError(f"Raw data for {self.window_size} not found! See docs.")

        # Load in expressed opinions list
        # expressed_opinions = {}

        # Iterate over records, creating graph
        for record in records(self.stream_dir, end_date="2023-05-28"):
            pass

        pass

    def simulate(self) -> t.Generator[tuple[str, dict[str, UserActivity]], None, None]:
        if not self.bsky_net:
            raise ValueError("BskyNet not built! Run `build()` first.")

        for step, data in self.bsky_net.items():
            yield step, data

    def _data_path(self) -> Path:
        path_parts = Path.cwd().parts

        root_idx = path_parts.index("bsky-net")
        curr_depth = len(path_parts) - root_idx - 1
        return Path("../" * curr_depth) / "data"


# bsky_net_daily = BskyNet(
#     window_size=TimeFormat.daily,
#     stream_dir="../data/stream",
#     start_date="2023-05-28",
#     end_date="2023-05-28",
# )
# bsky_net_daily.build()

# for step, data in bsky_net_daily.simulate():
#     print(step)
#     print(data)

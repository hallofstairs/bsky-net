# %% Imports

import json
import sys
import typing as t
from datetime import datetime, timedelta
from enum import Enum

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.artist import Artist
from matplotlib.collections import LineCollection

# %% Run bsky-net simulation


class TimeFormat(str, Enum):
    hourly = "%Y-%m-%d-%H"
    daily = "%Y-%m-%d"
    weekly = "%Y-%W"
    monthly = "%Y-%m"


def get_time_window(
    created_at: str, format: t.Literal["%Y-%m-%d-%H", "%Y-%m-%d", "%Y-%W", "%Y-%m"]
) -> str:
    """
    Get the relevant subset of a timestamp for a given grouping.

    e.g. "2023-01-01" for "daily, "2023-01" for "monthly"
    """
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime(format)


class Interaction(t.TypedDict):
    time: str  # TODO: Change name
    producer: str
    consumers: list[str]
    on_topic: bool
    opinion: t.Optional[t.Literal["against", "favor", "none"]]


interactions: list[Interaction] = []

with open("../data/processed/bsky-net-test.jsonl", "r") as f:
    interactions = [json.loads(line) for line in f]

users = set()

for interaction in interactions:
    users.add(interaction["producer"])
    users.update(interaction["consumers"])

# %%


def create_time_frames(interactions):
    start_time = datetime.fromisoformat(interactions[0]["time"])
    end_time = datetime.fromisoformat(interactions[-1]["time"])

    delta = end_time - start_time

    return [
        (start_time + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M")
        for i in range(int(delta.total_seconds() // 60) + 1)
    ]


time_frames = create_time_frames(interactions)

G = nx.Graph()
G.add_nodes_from(list(users))

pos = nx.random_layout(G)
node_pos = np.array([pos[n] for n in G.nodes])

fig, ax = plt.subplots(figsize=(10, 8))
fig.tight_layout(pad=3.0)
ax.axis("off")

nodes = ax.scatter(
    node_pos[:, 0], node_pos[:, 1], s=10, color="gray", alpha=0.1, edgecolors="black"
)
edge_collection = LineCollection([], colors=[], linewidths=3.0)
ax.add_collection(edge_collection)

edges: list = []
colors: list = []

interaction_idx = 0


def update_frame(frame_idx: int) -> list[Artist]:
    global edges, colors, interaction_idx

    ax.set_title(f"Time {time_frames[frame_idx]}")
    expired_index = -1

    # Update old lines
    for i in range(len(colors)):
        colors[i][3] -= 0.0225
        if colors[i][3] <= 0:
            expired_index = i

    if expired_index != -1:
        edges = edges[expired_index:]
        colors = colors[expired_index:]

    while True:
        interaction = interactions[interaction_idx]

        if interaction["time"][:16] != time_frames[frame_idx][:16]:
            break

        # Draw edges
        for target_node in interaction["consumers"]:
            edges.append([pos[interaction["producer"]], pos[target_node]])
            colors.append(
                [1.0, 0.0, 0.0, 0.25]
                if interaction["opinion"] == "against"
                else [0.0, 0.0, 1.0, 0.25]
                if interaction["opinion"] == "favor"
                else [0.5, 0.5, 0.5, 0.25]
            )

        interaction_idx += 1

    edge_collection.set_segments(edges)
    edge_collection.set_color(colors)

    return t.cast(list[Artist], ax.artists)


def timer_callback(current_frame: int, total_frames: int):
    sys.stdout.write(
        f"Building: {current_frame}/{total_frames} frames ({current_frame/total_frames*100:.2f}%)"
    )
    sys.stdout.flush()


anim = FuncAnimation(fig, update_frame, frames=len(time_frames), interval=1000)

anim.save(
    "animation.mp4", writer="ffmpeg", fps=30, dpi=100, progress_callback=timer_callback
)

# %%

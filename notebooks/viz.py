# TODO: This needs an inverse version of bsky-graph

# users = list(set([did for step in opinion_history.values() for did in step.keys()]))


# G = nx.Graph()
# G.add_nodes_from(list(users))

# pos = nx.random_layout(G)
# node_pos = np.array([pos[n] for n in G.nodes])

# fig, ax = plt.subplots(figsize=(10, 8))
# fig.tight_layout(pad=3.0)
# ax.axis("off")

# nodes = ax.scatter(
#     node_pos[:, 0], node_pos[:, 1], s=10, color="gray", alpha=0.1, edgecolors="black"
# )
# edge_collection = LineCollection([], colors=[], linewidths=3.0)
# ax.add_collection(edge_collection)

# edges: list = []
# colors: list = []

# interaction_idx = 0


# def update_frame(frame_idx: int) -> list[Artist]:
#     global edges, colors, interaction_idx

#     ax.set_title(f"Time {time_frames[frame_idx]}")
#     expired_index = -1

#     # Update old lines
#     for i in range(len(colors)):
#         colors[i][3] -= 0.0225
#         if colors[i][3] <= 0:
#             expired_index = i

#     if expired_index != -1:
#         edges = edges[expired_index:]
#         colors = colors[expired_index:]

#     while True:
#         interaction = interactions[interaction_idx]

#         if interaction["time"][:16] != time_frames[frame_idx][:16]:
#             break

#         # Draw edges
#         for target_node in interaction["consumers"]:
#             edges.append([pos[interaction["producer"]], pos[target_node]])
#             colors.append(
#                 [1.0, 0.0, 0.0, 0.25]
#                 if interaction["opinion"] == "against"
#                 else [0.0, 0.0, 1.0, 0.25]
#                 if interaction["opinion"] == "favor"
#                 else [0.5, 0.5, 0.5, 0.25]
#             )

#         interaction_idx += 1

#     edge_collection.set_segments(edges)
#     edge_collection.set_color(colors)

#     return t.cast(list[Artist], ax.artists)


# def timer_callback(current_frame: int, total_frames: int):
#     sys.stdout.write(
#         f"Building: {current_frame}/{total_frames} frames ({current_frame/total_frames*100:.2f}%)"
#     )
#     sys.stdout.flush()


# anim = FuncAnimation(fig, update_frame, frames=len(time_frames), interval=1000)

# anim.save(
#     "animation.mp4", writer="ffmpeg", fps=30, dpi=100, progress_callback=timer_callback
# )

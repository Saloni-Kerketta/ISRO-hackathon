"""
heatmaps.py
-----------
PURPOSE (in plain English):
    Turn the Betweenness Centrality scores (a dictionary of numbers)
    into actual PICTURES that are easy for judges to understand at a
    glance, instead of a table of decimals.

TWO KINDS OF HEATMAP, BOTH BUILT HERE:

    1. MAP-STYLE heatmap (geographic):
       Draws the road network exactly as it physically looks (using
       each node's x/y position), but colors and sizes each
       intersection according to its centrality score. Big red dots =
       critical Gatekeeper Nodes. Small blue dots = unimportant
       dead-ends. This is the one that looks impressive on a map and
       instantly tells a judge "THAT junction right there is the
       dangerous one."

    2. MATRIX-STYLE heatmap (shortest-path distance grid):
       A grid where row i, column j is colored by the shortest-path
       distance between node i and node j. This is a more
       "data-science-y" visual -- useful for explaining HOW
       betweenness centrality works under the hood (it's built from
       exactly these pairwise shortest paths), and for spotting
       overall network structure (clusters, isolated groups) at a
       glance. Less intuitive to a non-technical judge than the
       map-style one, but great backup material if someone asks
       "how did you actually compute this?"

Both functions save a PNG file you can drop straight into your slides
or report. Both also return the matplotlib figure object in case you
want to display it inline (e.g. in a Jupyter notebook) instead of
just saving it.
"""

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for headless/script use
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import networkx as nx
import numpy as np

from centrality import compute_betweenness_centrality


def plot_centrality_map(G, output_path="centrality_map.png", weight="weight",
                         k=None, pos_attrs=("x", "y"), title=None,
                         highlight_top_n=3):
    """
    Draws the road network using each node's actual x/y (or lat/lng)
    position, coloring and sizing nodes by their Betweenness
    Centrality score. This is the "geographic" heatmap.

    Parameters
    ----------
    G : networkx.Graph
        The road network. Each node MUST have position attributes
        (default assumes 'x' and 'y'; for a graph using pixel
        coordinates as node IDs like (row, col), see
        plot_centrality_map_from_pixel_nodes below instead).
    output_path : str
        Where to save the PNG.
    weight : str
        Edge attribute holding real-world road length, used in the
        centrality calculation.
    k : int or None
        k-sampling for large graphs (see centrality.py). Leave None
        for small/medium tiles.
    pos_attrs : tuple of str
        Names of the node attributes holding (x, y) position.
    title : str or None
        Plot title. Defaults to a generic one if not given.
    highlight_top_n : int
        Draws a label on the top N highest-centrality nodes so judges
        can immediately see which ones are the "Gatekeeper Nodes".

    Returns
    -------
    matplotlib.figure.Figure
    """
    scores = compute_betweenness_centrality(G, weight=weight, k=k)

    x_attr, y_attr = pos_attrs
    pos = {node: (data[x_attr], data[y_attr]) for node, data in G.nodes(data=True)}

    fig, ax = plt.subplots(figsize=(7, 7))

    # Draw edges first (thin gray lines) so they sit BEHIND the nodes.
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#999999", width=1.0, alpha=0.6)

    # Color scale: low centrality = cool color, high centrality = hot color.
    node_list = list(G.nodes())
    node_colors = [scores[n] for n in node_list]

    # Size scale: make the most critical nodes visibly BIGGER, not just
    # a different color -- redundant encoding helps people who are
    # colorblind or just skimming quickly.
    max_score = max(node_colors) if node_colors and max(node_colors) > 0 else 1.0
    node_sizes = [80 + 600 * (s / max_score) for s in node_colors]

    nodes = nx.draw_networkx_nodes(
        G, pos, ax=ax, nodelist=node_list,
        node_color=node_colors, node_size=node_sizes,
        cmap=matplotlib.colormaps["YlOrRd"], vmin=0, vmax=max_score,
        edgecolors="black", linewidths=0.5,
    )

    # Label the top N Gatekeeper Nodes directly on the map.
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    for node, score in ranked[:highlight_top_n]:
        x, y = pos[node]
        ax.annotate(
            f"Gatekeeper\n{score:.3f}", (x, y),
            textcoords="offset points", xytext=(10, 10),
            fontsize=8, fontweight="bold", color="darkred",
        )

    cbar = fig.colorbar(nodes, ax=ax, shrink=0.7)
    cbar.set_label("Betweenness Centrality (higher = more critical)")

    ax.set_title(title or "Intersection Criticality Heatmap", fontsize=14, fontweight="bold")
    ax.set_xlabel("X coordinate")
    ax.set_ylabel("Y coordinate")
    ax.set_aspect("equal")
    ax.margins(0.15)  # extra breathing room so edge labels aren't clipped

    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    print(f"Saved map-style heatmap to: {output_path}")
    return fig


def plot_centrality_map_from_pixel_nodes(G, output_path="centrality_map.png",
                                          weight="weight", k=None, title=None,
                                          highlight_top_n=3):
    """
    Same as plot_centrality_map, but for graphs where node IDs ARE the
    position -- i.e. each node is literally a (row, col) tuple, which
    is exactly the format Phase II's real .gpickle files use (we
    confirmed this from your uploaded 64_graph.gpickle). Most real
    tiles from your dataset will need THIS function, not the one
    above.

    Parameters are the same as plot_centrality_map, minus pos_attrs
    (not needed since position comes from the node ID itself).
    """
    scores = compute_betweenness_centrality(G, weight=weight, k=k)

    # Node IDs are (row, col). For a natural map look, we plot
    # col on the x-axis and use NEGATIVE row on the y-axis (so the
    # image isn't flipped upside-down -- row 0 is the TOP in image
    # coordinates, but the BOTTOM in standard plot coordinates).
    pos = {node: (node[1], -node[0]) for node in G.nodes()}

    fig, ax = plt.subplots(figsize=(7, 7))
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#999999", width=1.0, alpha=0.6)

    node_list = list(G.nodes())
    node_colors = [scores[n] for n in node_list]
    max_score = max(node_colors) if node_colors and max(node_colors) > 0 else 1.0
    node_sizes = [80 + 600 * (s / max_score) for s in node_colors]

    nodes = nx.draw_networkx_nodes(
        G, pos, ax=ax, nodelist=node_list,
        node_color=node_colors, node_size=node_sizes,
        cmap=matplotlib.colormaps["YlOrRd"], vmin=0, vmax=max_score,
        edgecolors="black", linewidths=0.5,
    )

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    for node, score in ranked[:highlight_top_n]:
        x, y = pos[node]
        ax.annotate(
            f"Gatekeeper\n{score:.3f}", (x, y),
            textcoords="offset points", xytext=(10, 10),
            fontsize=8, fontweight="bold", color="darkred",
        )

    cbar = fig.colorbar(nodes, ax=ax, shrink=0.7)
    cbar.set_label("Betweenness Centrality (higher = more critical)")

    ax.set_title(title or "Intersection Criticality Heatmap", fontsize=14, fontweight="bold")
    ax.set_xlabel("pixel column")
    ax.set_ylabel("pixel row (inverted)")
    ax.set_aspect("equal")
    ax.margins(0.15)  # extra breathing room so edge labels aren't clipped

    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    print(f"Saved map-style heatmap to: {output_path}")
    return fig


def plot_distance_matrix_heatmap(G, output_path="distance_matrix.png",
                                  weight="weight", title=None):
    """
    Draws the MATRIX-style heatmap: an NxN grid where cell (i, j) is
    colored by the shortest-path distance between node i and node j.
    Diagonal is always 0 (a node's distance to itself).
    Bright/light cells = far apart. Dark cells = close together.
    White or blank cells = genuinely unreachable (disconnected).

    This is less intuitive than the map-style heatmap for a
    non-technical audience, but useful as backup/technical-depth
    material, and for visually spotting if the graph has separate
    "islands" (you'll see distinct dark blocks along the diagonal
    with bright/blank space between them).

    Parameters
    ----------
    G : networkx.Graph
        The road network.
    output_path : str
        Where to save the PNG.
    weight : str
        Edge attribute holding real-world road length.
    title : str or None
        Plot title.

    Returns
    -------
    matplotlib.figure.Figure
    """
    nodes = list(G.nodes())
    n = len(nodes)
    node_index = {node: i for i, node in enumerate(nodes)}

    # Start with NaN everywhere -- this lets us visually distinguish
    # "unreachable" (stays NaN, shows as blank/white) from "reachable
    # but far" (a real large number).
    matrix = np.full((n, n), np.nan)

    for source, distances in nx.all_pairs_dijkstra_path_length(G, weight=weight):
        i = node_index[source]
        for target, dist in distances.items():
            j = node_index[target]
            matrix[i, j] = dist

    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = matplotlib.colormaps["viridis"].copy()
    cmap.set_bad(color="white")  # NaN (unreachable) cells render white

    im = ax.imshow(matrix, cmap=cmap)
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Shortest-path distance (meters) -- white = unreachable")

    ax.set_title(title or "Pairwise Shortest-Path Distance Matrix", fontsize=13, fontweight="bold")
    ax.set_xlabel("Node index (target)")
    ax.set_ylabel("Node index (source)")

    fig.tight_layout()
    fig.savefig(output_path, dpi=100)
    print(f"Saved matrix-style heatmap to: {output_path}")
    return fig


if __name__ == "__main__":
    # Quick manual test on the real tile-64 graph (node IDs are
    # (row, col) pixel tuples, so we use the pixel-node version).
    import pickle

    with open("/mnt/user-data/uploads/64_graph.gpickle", "rb") as f:
        G = pickle.load(f)

    plot_centrality_map_from_pixel_nodes(
        G, output_path="/home/claude/centrality_map_tile64.png",
        title="Tile 64 -- Criticality Heatmap"
    )
    plot_distance_matrix_heatmap(
        G, output_path="/home/claude/distance_matrix_tile64.png",
        title="Tile 64 -- Distance Matrix"
    )

    # Also test on the toy city (uses x/y attributes, not pixel-tuple
    # node IDs) to confirm the other function works too.
    from toy_city import build_toy_city
    G_toy = build_toy_city()
    plot_centrality_map(
        G_toy, output_path="/home/claude/centrality_map_toycity.png",
        title="Toy City -- Criticality Heatmap"
    )
    plot_distance_matrix_heatmap(
        G_toy, output_path="/home/claude/distance_matrix_toycity.png",
        title="Toy City -- Distance Matrix"
    )
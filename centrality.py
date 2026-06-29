"""
centrality.py
--------------
PURPOSE (in plain English):
    Look at the whole city graph and figure out which intersections are
    the most "important" — meaning, the most shortest-routes between
    OTHER intersections pass through them.

    These important intersections are what the problem statement calls
    "Gatekeeper Nodes". If a Gatekeeper Node shuts down (flood, accident),
    lots of routes across the city are forced into long detours.

THE MATH (you don't need to implement this by hand -- NetworkX does it):
    For every pair of nodes (s, t) in the city, NetworkX finds the
    shortest path between them. Then for every node v, it counts:
    "out of all the shortest paths between every pair of nodes,
     how many of them pass through v?"

    A node that sits on MANY shortest paths gets a HIGH score.
    A node off to the side, on a dead-end street, gets a LOW score.

    This score is called "Betweenness Centrality" and NetworkX gives it
    to us with one function call: nx.betweenness_centrality(G)
"""

import networkx as nx


def compute_betweenness_centrality(G, weight="weight", k=None, seed=42):
    """
    Calculates Betweenness Centrality for every node in the graph.

    Parameters
    ----------
    G : networkx.Graph
        The healed road network graph from Phase II.
        Every edge MUST have a 'weight' attribute (real-world length
        in meters) -- Phase II already provides this.

    weight : str
        The name of the edge attribute holding the road's physical
        length. Default is "weight" because that's what Phase II uses.
        (Without this, NetworkX would just count number of road
        segments, not actual distance -- which would be wrong, since a
        50m residential road and a 2km highway are very different.)

    k : int or None
        For big city graphs (tens of thousands of nodes), computing
        EXACT centrality is slow. Setting k=500 (as the problem
        statement suggests) tells NetworkX: "Don't check literally
        every pair of nodes -- just randomly sample 500 source nodes
        and estimate from that." This is called k-sampling
        approximation. For your toy graph (9 nodes) or small demo
        areas, leave k=None to get the exact answer.

    seed : int
        Only matters when k is not None. Makes the random sampling
        reproducible -- i.e., running it twice gives the same result,
        which you want for a stable demo.

    Returns
    -------
    dict
        {node_id: centrality_score, ...}
        Higher score = more "important"/bottleneck-like.
        Scores are normalized between 0 and 1 by default in NetworkX.
    """
    centrality_scores = nx.betweenness_centrality(
        G, weight=weight, k=k, seed=seed, normalized=True
    )
    return centrality_scores


def get_top_gatekeepers(G, top_n=5, weight="weight", k=None):
    """
    Returns the top_n most critical "Gatekeeper Nodes" in the city,
    sorted from most critical to least critical.

    Parameters
    ----------
    G : networkx.Graph
        The road network graph.
    top_n : int
        How many top nodes you want back (e.g. top 5 Gatekeepers).
    weight, k : see compute_betweenness_centrality above.

    Returns
    -------
    list of tuples
        [(node_id, score), (node_id, score), ...]
        sorted highest score first.
    """
    scores = compute_betweenness_centrality(G, weight=weight, k=k)

    # sorted() with reverse=True puts the HIGHEST score first.
    # key=lambda item: item[1] tells Python "sort by the score part
    # of each (node_id, score) pair, not by the node_id itself."
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    return ranked[:top_n]


if __name__ == "__main__":
    # quick manual test using the toy city -- run this file directly
    # with: python3 centrality.py
    from toy_city import build_toy_city

    G = build_toy_city()
    scores = compute_betweenness_centrality(G)

    print("Betweenness Centrality scores for every node:")
    for node, score in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"  {node}: {score:.3f}")

    print()
    top = get_top_gatekeepers(G, top_n=3)
    print("Top 3 Gatekeeper Nodes:", top)
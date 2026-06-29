"""
resilience.py
-------------
PURPOSE (in plain English):
    Take the healed city graph and answer: "If this intersection gets
    knocked out (flood, accident, construction), how much WORSE does
    travel get across the whole city?"

    We answer this in 3 steps:
      1. Measure how efficient the WHOLE city graph is right now
         (before anything bad happens) -> this is the "baseline".
      2. Pretend a node is destroyed: delete it from a COPY of the graph.
      3. Measure efficiency again on the damaged graph -> this is the
         "perturbed" (disturbed) state.

    Then:
        Resilience Index = perturbed_efficiency / baseline_efficiency

    If this ratio is close to 1.0  -> city barely noticed, very resilient.
    If this ratio crashes toward 0 -> city fell apart, very fragile.

KEY IDEA YOU MUST UNDERSTAND -- "Global Efficiency":
    We can't just average the shortest-path DISTANCE between every pair
    of nodes, because if a flood disconnects part of the city, the
    distance between some pairs becomes INFINITE (no path exists at
    all). Averaging with infinity in the mix breaks instantly.

    The fix: average the INVERSE of distance (i.e. 1/distance) instead.
        - close nodes  -> 1/distance is a BIG number  -> "efficient"
        - far nodes    -> 1/distance is a SMALL number -> "less efficient"
        - unreachable  -> 1/infinity = 0               -> contributes
          NOTHING to the average, with no crash, no special-casing.

    This is exactly the E_global formula from the problem statement:
        E_global(G) = (1 / (n*(n-1))) * sum( 1/d(i,j) for all i != j )
"""

import networkx as nx
from centrality import compute_betweenness_centrality, get_top_gatekeepers


def compute_global_efficiency(G, weight="weight"):
    """
    Calculates the Global Efficiency of a graph -- a single number
    summarizing "how easily can traffic flow between any two
    intersections in this city, on average?"

    Parameters
    ----------
    G : networkx.Graph
        The road network. Can be the full healthy graph, or a
        graph with some nodes already removed (damaged).
    weight : str
        Edge attribute holding real-world road length in meters.
        We use real distances, not just "number of hops", because a
        500m road and a 50m road are not equally costly to travel.

    Returns
    -------
    float
        Global efficiency score. Conveniently, NetworkX already
        implements exactly this formula for us:
        nx.global_efficiency(G)
        NOTE: nx.global_efficiency does NOT support a `weight`
        parameter directly (it assumes hop-distance = 1 per edge).
        Since our problem statement explicitly wants REAL-WORLD
        distances, we compute it manually below using weighted
        shortest paths, instead of relying on the unweighted
        built-in.
    """
    nodes = list(G.nodes())
    n = len(nodes)

    # Can't compute efficiency for an empty or single-node graph --
    # there are no pairs to compare. Return 0 to signal "fully broken".
    if n <= 1:
        return 0.0

    # nx.all_pairs_dijkstra_path_length gives us, for every node,
    # the shortest weighted distance to every OTHER node it can reach.
    # If two nodes are disconnected, the unreachable one simply won't
    # appear in that dictionary at all (not even as "infinity") --
    # so we treat "not present" as "infinite distance" -> contributes 0.
    total = 0.0
    for source, distances in nx.all_pairs_dijkstra_path_length(G, weight=weight):
        for target, dist in distances.items():
            if source != target and dist > 0:
                total += 1.0 / dist
            # if dist == 0 (shouldn't happen for source != target) we
            # just skip it safely.

    efficiency = total / (n * (n - 1))
    return efficiency


def simulate_node_failure(G, node_to_remove, weight="weight"):
    """
    Simulates a single intersection being knocked out (flood, accident)
    and returns the city's efficiency AFTER that failure.

    IMPORTANT: this does NOT modify your original graph G. It works on
    a copy, because you'll want to run this simulation many times on
    the same original healthy graph (once per candidate Gatekeeper),
    and you don't want one simulation's damage to carry over into the
    next one.

    Parameters
    ----------
    G : networkx.Graph
        The original, healthy road network.
    node_to_remove : node id
        The intersection to "destroy" (e.g. the clicked node from the
        map, or a Gatekeeper Node you're stress-testing).
    weight : str
        Edge attribute holding real-world road length.

    Returns
    -------
    float
        Global efficiency of the damaged graph.
    """
    G_damaged = G.copy()          # never touch the original graph
    G_damaged.remove_node(node_to_remove)
    return compute_global_efficiency(G_damaged, weight=weight)


def compute_resilience_index(G, node_to_remove, weight="weight"):
    """
    THE headline metric of Phase III.

    Compares the city's efficiency before and after a specific
    intersection fails, and returns a single ratio:

        Resilience Index = efficiency_after / efficiency_before

    Parameters
    ----------
    G : networkx.Graph
        The original, healthy road network (untouched).
    node_to_remove : node id
        The intersection being "destroyed" in this simulation.
    weight : str
        Edge attribute holding real-world road length.

    Returns
    -------
    dict with keys:
        'baseline_efficiency'   : float, efficiency before failure
        'perturbed_efficiency'  : float, efficiency after failure
        'resilience_index'      : float, the ratio (0 to 1, roughly)
        'node_removed'          : the node that was simulated as failed
    """
    baseline = compute_global_efficiency(G, weight=weight)
    perturbed = simulate_node_failure(G, node_to_remove, weight=weight)

    # Guard against division by zero -- if the baseline itself is 0
    # (e.g. a completely disconnected starting graph), the ratio is
    # undefined, so we report 0.0 rather than crashing.
    if baseline == 0:
        resilience_index = 0.0
    else:
        resilience_index = perturbed / baseline

    return {
        "node_removed": node_to_remove,
        "baseline_efficiency": baseline,
        "perturbed_efficiency": perturbed,
        "resilience_index": resilience_index,
    }


def stress_test_top_gatekeepers(G, top_n=5, weight="weight", k=None):
    """
    Convenience function that ties Phase III together end-to-end:
      1. Finds the top_n Gatekeeper Nodes (highest betweenness
         centrality) using centrality.py
      2. Simulates removing EACH ONE individually
      3. Reports the Resilience Index for each

    This is what your dashboard (Phase IV) will likely call directly,
    e.g. to pre-populate "here are the 5 most dangerous intersections
    in this city, and here's what happens if each one floods."

    Parameters
    ----------
    G : networkx.Graph
        The healed road network.
    top_n : int
        How many top Gatekeeper Nodes to stress-test.
    weight, k : see centrality.py for explanation.

    Returns
    -------
    list of dict
        One result dict (same shape as compute_resilience_index)
        per Gatekeeper Node, sorted from most damaging to least.
    """
    gatekeepers = get_top_gatekeepers(G, top_n=top_n, weight=weight, k=k)
    baseline = compute_global_efficiency(G, weight=weight)

    results = []
    for node, centrality_score in gatekeepers:
        perturbed = simulate_node_failure(G, node, weight=weight)
        resilience_index = (perturbed / baseline) if baseline > 0 else 0.0

        results.append({
            "node_removed": node,
            "centrality_score": centrality_score,
            "baseline_efficiency": baseline,
            "perturbed_efficiency": perturbed,
            "resilience_index": resilience_index,
        })

    # sort so the MOST damaging failure (lowest resilience index)
    # appears first -- that's the most "dangerous" intersection.
    results.sort(key=lambda r: r["resilience_index"])
    return results


def ablate_node_live(G, node_to_remove, weight="weight"):
    """
    THIS IS THE FUNCTION YOUR DASHBOARD (PHASE IV) WILL CALL.

    When a user clicks an intersection on the live map, Phase IV's
    backend will call this ONE function with the node they clicked.
    It returns everything the dashboard needs to update the screen:
      - the new Resilience Index
      - the damaged graph itself (so the map can redraw which roads
        are now part of detour routes)
      - which nodes became completely unreachable, if any (e.g. an
        isolated neighborhood cut off by the flood)

    Speed note: for a live click-and-respond demo, this function must
    run in well under a second. compute_global_efficiency() is the
    expensive part (it checks every pair of nodes). For a graph with
    tens of thousands of nodes, you MUST restrict it -- see the
    "k-sampling" pattern in centrality.py, and consider precomputing
    baseline_efficiency once at app startup rather than recomputing
    it on every single click (the baseline never changes, only the
    perturbed graph does).

    Parameters
    ----------
    G : networkx.Graph
        The original healthy road network (never modified).
    node_to_remove : node id
        The intersection the user clicked.
    weight : str
        Edge attribute holding real-world road length.

    Returns
    -------
    dict with keys:
        'resilience_index'     : float
        'baseline_efficiency'  : float
        'perturbed_efficiency' : float
        'damaged_graph'        : networkx.Graph (G with the node removed)
        'disconnected_nodes'   : list of nodes that became unreachable
                                  from the main network after the failure
    """
    baseline = compute_global_efficiency(G, weight=weight)

    G_damaged = G.copy()
    G_damaged.remove_node(node_to_remove)

    perturbed = compute_global_efficiency(G_damaged, weight=weight)
    resilience_index = (perturbed / baseline) if baseline > 0 else 0.0

    # Find out if the failure split the city into separate "islands".
    # nx.connected_components groups nodes into clusters that can still
    # reach each other. If there's more than 1 cluster, some part of
    # the city got cut off entirely -- the dashboard will want to
    # highlight this as a critical alert, not just a slowdown.
    components = list(nx.connected_components(G_damaged))
    disconnected_nodes = []
    if len(components) > 1:
        # the largest component is presumably "the rest of the city
        # still functioning normally" -- anything outside it is cut off.
        largest = max(components, key=len)
        for component in components:
            if component is not largest:
                disconnected_nodes.extend(component)

    return {
        "resilience_index": resilience_index,
        "baseline_efficiency": baseline,
        "perturbed_efficiency": perturbed,
        "damaged_graph": G_damaged,
        "disconnected_nodes": disconnected_nodes,
    }


if __name__ == "__main__":
    # quick manual test using the toy city -- run with:
    # python3 resilience.py
    from toy_city import build_toy_city

    G = build_toy_city()

    print("=== Single node failure test ===")
    result = compute_resilience_index(G, node_to_remove="E")
    print(f"Removing node 'E' (the center, expected to be the worst):")
    for key, value in result.items():
        print(f"  {key}: {value}")

    print()
    result2 = compute_resilience_index(G, node_to_remove="A")
    print(f"Removing node 'A' (a corner, expected to be mild):")
    for key, value in result2.items():
        print(f"  {key}: {value}")

    print()
    print("=== Full stress test on top 3 Gatekeepers ===")
    results = stress_test_top_gatekeepers(G, top_n=3)
    for r in results:
        print(f"  Node {r['node_removed']}: centrality={r['centrality_score']:.3f}, "
              f"resilience_index={r['resilience_index']:.3f}")
"""
run_phase3.py
-------------
THIS IS THE ONE FILE YOU ACTUALLY RUN.

It does all 4 steps of Phase III, in order, on a single tile:

    1. Load the .gpickle graph file
    2. Convert pixel weights -> real-world meters (geo_utils.py)
    3. Find the Gatekeeper Nodes (centrality.py)
    4. Run the stress test / Resilience Index (resilience.py)

Usage:
    python3 run_phase3.py /path/to/your_graph.gpickle

If you don't pass a path, it defaults to the tile-64 example so you
can test that the script itself works.
"""

import sys
import pickle

from geo_utils import convert_weights_accurate
from centrality import get_top_gatekeepers
from resilience import compute_global_efficiency, stress_test_top_gatekeepers


# ---------------------------------------------------------------------------
# SETTINGS YOU MAY NEED TO CHANGE
# ---------------------------------------------------------------------------
# Meters per pixel for whatever satellite/dataset produced this tile.
# Ask your Phase I/II teammate which one it is. Common values:
#   Cartosat-3 (high-res)    : ~0.3
#   SpaceNet/DeepGlobe       : ~0.3 - 0.5
#   Resourcesat LISS-IV      : ~5.8
#   Sentinel-2               : ~10
GSD_METERS_PER_PIXEL = 0.3

# How many top Gatekeeper Nodes to find and stress-test.
TOP_N_GATEKEEPERS = 5
# ---------------------------------------------------------------------------


def run_phase3_on_tile(gpickle_path, gsd=GSD_METERS_PER_PIXEL, top_n=TOP_N_GATEKEEPERS):
    """
    Runs the full Phase III pipeline on one tile and prints a clean
    summary. This is the function to call -- everything else in this
    file is just plumbing around it.
    """
    print(f"Loading graph from: {gpickle_path}")
    with open(gpickle_path, "rb") as f:
        G = pickle.load(f)

    print(f"  -> {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    import networkx as nx
    n_components = nx.number_connected_components(G)
    print(f"  -> {n_components} connected component(s)")
    if n_components > 1:
        print("  WARNING: this graph is split into multiple disconnected "
              "pieces. Centrality and resilience results below only "
              "apply WITHIN each piece -- there's no 'bottleneck' "
              "connecting pieces that aren't connected at all.")

    print()
    print("Step 2: converting pixel weights to real-world meters...")
    G_meters = convert_weights_accurate(G, gsd_meters_per_pixel=gsd)
    print(f"  -> using {gsd} meters/pixel")

    print()
    print(f"Step 3: finding top {top_n} Gatekeeper Nodes...")
    gatekeepers = get_top_gatekeepers(G_meters, top_n=top_n)
    if not gatekeepers or gatekeepers[0][1] == 0:
        print("  -> no meaningful bottlenecks found (graph may be too "
              "small, too sparse, or fully disconnected into separate "
              "pieces with no node 'between' any others).")
    else:
        for node, score in gatekeepers:
            print(f"  -> node {node}: centrality score = {score:.4f}")

    print()
    print("Step 4: running stress test (simulating each Gatekeeper failing)...")
    baseline = compute_global_efficiency(G_meters)
    print(f"  -> baseline Global Efficiency: {baseline:.6f}")

    if baseline == 0:
        print("  -> baseline efficiency is 0 (graph has no usable paths "
              "between nodes). Cannot compute a meaningful Resilience "
              "Index for this tile.")
        return

    results = stress_test_top_gatekeepers(G_meters, top_n=top_n)
    print()
    print("Results (sorted worst-case first):")
    print(f"  {'Node':<20} {'Centrality':<12} {'Resilience Index':<18}")
    for r in results:
        node_str = str(r["node_removed"])
        print(f"  {node_str:<20} {r['centrality_score']:<12.4f} {r['resilience_index']:<18.4f}")

    if results:
        worst = results[0]
        print()
        print(f"MOST CRITICAL NODE: {worst['node_removed']}")
        print(f"  If this intersection fails, Global Efficiency drops to "
              f"{worst['resilience_index']*100:.1f}% of normal "
              f"({(1 - worst['resilience_index'])*100:.1f}% efficiency loss).")


def run_phase3_on_tile_quiet(gpickle_path, gsd=GSD_METERS_PER_PIXEL, top_n=TOP_N_GATEKEEPERS):
    """
    Same pipeline as run_phase3_on_tile, but SILENT -- no print statements.
    Instead it returns a small dictionary summarizing the result.

    This is the version meant for BATCH processing: when you have many
    .gpickle files and want to scan all of them quickly to find the
    best demo candidates, printing a full wall of text per file would
    be unreadable. Use this function in a loop instead (see
    run_batch.py), and print one summary table at the end.

    Returns
    -------
    dict with keys:
        'file'                : the filename (without path)
        'n_nodes', 'n_edges'  : graph size
        'n_components'        : how many disconnected pieces
        'top_gatekeeper'      : the node id with highest centrality
                                 (or None if no meaningful bottleneck)
        'top_centrality'      : that node's centrality score
        'worst_resilience'    : the lowest (most damaging) resilience
                                 index among the tested gatekeepers
        'baseline_efficiency' : the tile's baseline Global Efficiency
        'status'              : 'ok', 'too_small', or 'error'
        'error_message'       : only present if status == 'error'
    """
    import os
    import networkx as nx

    filename = os.path.basename(gpickle_path)

    try:
        with open(gpickle_path, "rb") as f:
            G = pickle.load(f)
    except Exception as e:
        return {"file": filename, "status": "error", "error_message": str(e)}

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if n_nodes < 3 or n_edges < 2:
        # Too small to have any meaningful bottleneck -- skip the
        # expensive calculations entirely, same conclusion either way.
        return {
            "file": filename, "n_nodes": n_nodes, "n_edges": n_edges,
            "n_components": nx.number_connected_components(G) if n_nodes > 0 else 0,
            "top_gatekeeper": None, "top_centrality": 0.0,
            "worst_resilience": None, "baseline_efficiency": None,
            "status": "too_small",
        }

    n_components = nx.number_connected_components(G)

    try:
        G_meters = convert_weights_accurate(G, gsd_meters_per_pixel=gsd)
        gatekeepers = get_top_gatekeepers(G_meters, top_n=top_n)
        baseline = compute_global_efficiency(G_meters)

        if not gatekeepers or baseline == 0:
            return {
                "file": filename, "n_nodes": n_nodes, "n_edges": n_edges,
                "n_components": n_components,
                "top_gatekeeper": None, "top_centrality": 0.0,
                "worst_resilience": None, "baseline_efficiency": baseline,
                "status": "too_small",
            }

        results = stress_test_top_gatekeepers(G_meters, top_n=top_n)
        worst = results[0]  # already sorted worst-first

        return {
            "file": filename, "n_nodes": n_nodes, "n_edges": n_edges,
            "n_components": n_components,
            "top_gatekeeper": gatekeepers[0][0],
            "top_centrality": gatekeepers[0][1],
            "worst_resilience": worst["resilience_index"],
            "baseline_efficiency": baseline,
            "status": "ok",
        }
    except Exception as e:
        return {"file": filename, "status": "error", "error_message": str(e)}


if __name__ == "__main__":
    # Allow passing a file path on the command line, e.g.:
    #   python3 run_phase3.py /mnt/user-data/uploads/64_graph.gpickle
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "graph/64_graph.gpickle"
        print(f"(No file path given, defaulting to: {path})")
        print()

    run_phase3_on_tile(path)
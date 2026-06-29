# Phase III: Network Vulnerability & Stress Testing

This folder contains everything for **Phase III** of Route Resilience.
It does NOT depend on Phase I (deep learning) or Phase II (skeletonization
+ healing) to be *finished* — it only needs their **output**: a NetworkX
graph where every edge has a `weight` attribute (real-world length in
meters). Until you get that graph, use `toy_city.py` to test everything.

## Files

| File | What it does |
|---|---|
| `toy_city.py` | A small fake 3x3 grid city, used ONLY for testing. Not part of the final submission, but keep it during development. |
| `centrality.py` | Finds the most critical intersections ("Gatekeeper Nodes"). |
| `resilience.py` | Simulates a node failing, and computes the Resilience Index. |

## How to test it right now (no real data needed)

```bash
cd graph_engine
python3 centrality.py     # prints centrality scores for the toy city
python3 resilience.py     # prints resilience index results
```

If both run without errors and the printed numbers make sense (the
center node "E" has the highest centrality, and removing it hurts the
city more than removing a corner), Phase III's core logic is correct.

## How to plug in the REAL graph from Phase II

Whoever does Phase II will hand you a `networkx.Graph` object, most
likely loaded from a `.pkl` (pickle) file. Here's the only thing that
matters: **every edge needs a `weight` attribute**, and it must already
be in real-world meters (Phase II's spec says they extract this from
GeoTIFF resolution metadata using `rasterio`, so this should already be
true — just double check by printing one edge).

```python
import pickle
import networkx as nx
from centrality import get_top_gatekeepers
from resilience import ablate_node_live, stress_test_top_gatekeepers

# Load Phase II's output
with open("healed_bengaluru_graph.pkl", "rb") as f:
    G = pickle.load(f)

# Sanity check: confirm edges have weights (run this once, manually)
sample_edge = list(G.edges(data=True))[0]
print(sample_edge)
# should look like: ('node_123', 'node_456', {'weight': 87.4, ...})
# if 'weight' is missing, ask the Phase II person to add it before
# you continue -- everything in Phase III depends on it.

# Find the top 5 most critical intersections in the real city
top_gatekeepers = get_top_gatekeepers(G, top_n=5)
print(top_gatekeepers)

# Run the full stress test (centrality + simulated failure for each)
results = stress_test_top_gatekeepers(G, top_n=5)
for r in results:
    print(r)
```

### IMPORTANT — for large real graphs (thousands of nodes)

`compute_betweenness_centrality` and `compute_global_efficiency` both
check EVERY pair of nodes by default, which gets slow once your graph
has thousands of nodes (a real city will). Two things to do:

1. **Use k-sampling for centrality.** Instead of `get_top_gatekeepers(G, top_n=5)`,
   call `get_top_gatekeepers(G, top_n=5, k=500)`. This tells NetworkX
   to estimate using only 500 random source nodes instead of literally
   every node — much faster, still accurate enough for a demo.

2. **Precompute the baseline efficiency once, not on every click.**
   The baseline (the healthy, undamaged city) never changes — only the
   damaged version changes when someone clicks a new intersection.
   When you wire this into Phase IV's FastAPI backend, compute
   `baseline_efficiency = compute_global_efficiency(G)` ONE time when
   the app starts up, store it, and reuse it on every click instead of
   recalculating it every single time. This is the difference between
   a snappy demo and a laggy one.

## What Phase IV (the dashboard person) needs to call

Tell them about exactly one function: `ablate_node_live(G, clicked_node)`
in `resilience.py`. It takes the graph and whichever node the user
clicked on the map, and returns a dictionary with the new resilience
index, the damaged graph (to redraw routes), and a list of any
neighborhoods that got completely cut off. That's the only integration
point they need.

```python
from resilience import ablate_node_live

result = ablate_node_live(G, clicked_node_id)
print(result["resilience_index"])      # e.g. 0.52 -> show this number
print(result["disconnected_nodes"])    # e.g. ["island_1", "island_2"]
                                        # -> highlight these in red/alert
```

## Concepts cheat-sheet (for explaining this to judges)

- **Betweenness Centrality**: for every intersection, count how many
  shortest routes between OTHER intersections pass through it. High
  count = critical bottleneck = "Gatekeeper Node."
- **Global Efficiency**: a single 0-to-~1 score for "how easily can
  the WHOLE city get around right now." Calculated by averaging
  `1/distance` between every pair of intersections (using the inverse
  so that disconnected/unreachable pairs contribute exactly 0, instead
  of breaking the average with infinity).
- **Resilience Index**: `efficiency_after_failure / efficiency_before_failure`.
  Close to 1.0 = city barely noticed. Drops toward 0 = city is fragile;
  this one intersection failing causes serious citywide gridlock.

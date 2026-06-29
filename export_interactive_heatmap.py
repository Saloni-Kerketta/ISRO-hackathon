"""
export_interactive_heatmap.py
-------------------------------
PURPOSE (in plain English):
    Takes any real .gpickle tile and generates a single, self-contained
    HTML file with an INTERACTIVE map: click any intersection, and it
    shows that node's centrality score and what the Resilience Index
    would become if that intersection failed.

    This is the "Click on any intersection" experience from the
    Section 9 demo script -- but as a standalone HTML file you can
    open in any browser, present on a projector, or embed inside
    Phase IV's dashboard if useful, WITHOUT needing a live Python
    backend running during the demo. All centrality scores and
    resilience outcomes are precomputed and baked into the file ahead
    of time, so clicking is instant (no live computation -> no lag
    during judging, satisfying Section 10's "live inference is too
    slow" risk mitigation).

    Note: for the REAL live dashboard demo described in the problem
    statement (where a flooded intersection redraws detour ROUTES,
    not just shows a number), Phase IV's FastAPI backend should call
    resilience.ablate_node_live() directly -- that gives a live,
    fresh computation. This script is for a simpler "explore the
    criticality map" companion view, or a fallback if live compute is
    too slow/risky during judging.

Usage:
    python3 export_interactive_heatmap.py /path/to/tile.gpickle output.html
"""

import sys
import json
import pickle

from geo_utils import convert_weights_accurate
from centrality import compute_betweenness_centrality
from resilience import compute_global_efficiency, ablate_node_live


def build_widget_data(gpickle_path, gsd_meters_per_pixel=0.3, k=None):
    """
    Loads a tile and precomputes everything the HTML widget needs:
    every node's position, centrality score, and the Resilience Index
    that would result if THAT specific node were removed.

    For graphs where node IDs are (row, col) pixel tuples (the format
    your real Phase II tiles use), position comes directly from the
    node ID. Skips the resilience pre-computation for very large
    graphs (>300 nodes) since recomputing efficiency for every single
    node would be slow -- in that case, only centrality is shown, and
    clicking shows "click triggers live simulation in the real
    dashboard" instead of a precomputed number.

    Returns
    -------
    dict, JSON-serializable, ready to embed in the HTML widget.
    """
    with open(gpickle_path, "rb") as f:
        G = pickle.load(f)

    G_meters = convert_weights_accurate(G, gsd_meters_per_pixel=gsd_meters_per_pixel)
    scores = compute_betweenness_centrality(G_meters, k=k)
    baseline = compute_global_efficiency(G_meters)

    n_nodes = G.number_of_nodes()
    precompute_resilience = n_nodes <= 300  # safety limit for speed

    nodes_data = []
    for node, attrs in G.nodes(data=True):
        # Node position: prefer explicit x/y attributes if present,
        # otherwise assume the node ID itself is a (row, col) tuple
        # (this is the format real Phase II tiles use).
        if "x" in attrs and "y" in attrs:
            x, y = attrs["x"], attrs["y"]
        elif isinstance(node, tuple) and len(node) == 2:
            row, col = node
            x, y = col, -row  # flip row so image isn't upside down
        else:
            x, y = 0, 0  # fallback, shouldn't normally happen

        entry = {
            "id": str(node),
            "x": x,
            "y": y,
            "centrality": round(scores.get(node, 0.0), 4),
        }

        if precompute_resilience and baseline > 0:
            result = ablate_node_live(G_meters, node)
            entry["resilience_if_removed"] = round(result["resilience_index"], 4)
            entry["disconnected_if_removed"] = [str(n) for n in result["disconnected_nodes"]]
        else:
            entry["resilience_if_removed"] = None
            entry["disconnected_if_removed"] = []

        nodes_data.append(entry)

    edges_data = [{"source": str(u), "target": str(v)} for u, v in G.edges()]

    return {
        "nodes": nodes_data,
        "edges": edges_data,
        "baseline_efficiency": round(baseline, 6) if baseline else 0,
        "precomputed_resilience": precompute_resilience,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Route Resilience -- Interactive Criticality Map</title>
<style>
  body { font-family: -apple-system, sans-serif; margin: 0; padding: 24px; background: #fafafa; }
  h1 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
  p.sub { font-size: 13px; color: #666; margin: 0 0 20px; }
  .layout { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; }
  svg { background: white; border: 1px solid #ddd; border-radius: 8px; }
  .panel { flex: 1; min-width: 220px; display: flex; flex-direction: column; gap: 10px; }
  .card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
  .card .label { font-size: 12px; color: #777; }
  .card .value { font-size: 20px; font-weight: 600; margin-top: 2px; }
  button { padding: 8px 14px; border-radius: 6px; border: 1px solid #ccc; background: white; cursor: pointer; }
  circle { cursor: pointer; }
</style>
</head>
<body>
  <h1>Intersection Criticality Heatmap</h1>
  <p class="sub">Click any intersection to see its centrality score and the Resilience Index if it fails.</p>
  <div class="layout">
    <svg id="mapSvg" viewBox="VIEWBOX_PLACEHOLDER" width="500" height="500"></svg>
    <div class="panel">
      <div class="card"><div class="label">Selected node</div><div class="value" id="selNode">none</div></div>
      <div class="card"><div class="label">Centrality score</div><div class="value" id="selCentrality">-</div></div>
      <div class="card"><div class="label">Resilience index if removed</div><div class="value" id="selResilience">-</div></div>
      <button id="resetBtn">Reset</button>
    </div>
  </div>
<script>
const data = DATA_PLACEHOLDER;
const nodeById = {};
data.nodes.forEach(n => nodeById[n.id] = n);

function colorForCentrality(c, maxC) {
  const t = maxC > 0 ? c / maxC : 0;
  const stops = ['#FAECE7', '#F5C4B3', '#F0997B', '#D85A30', '#993C1D'];
  const idx = Math.min(stops.length - 1, Math.floor(t * (stops.length - 1)));
  return stops[idx];
}

const svg = document.getElementById('mapSvg');
const maxC = Math.max(...data.nodes.map(n => n.centrality), 0.0001);

data.edges.forEach(e => {
  const a = nodeById[e.source], b = nodeById[e.target];
  if (!a || !b) return;
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', a.x); line.setAttribute('y1', a.y);
  line.setAttribute('x2', b.x); line.setAttribute('y2', b.y);
  line.setAttribute('stroke', '#ccc');
  line.setAttribute('stroke-width', '1.5');
  svg.appendChild(line);
});

data.nodes.forEach(n => {
  const r = 3 + 10 * (n.centrality / maxC);
  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', n.x);
  circle.setAttribute('cy', n.y);
  circle.setAttribute('r', r);
  circle.setAttribute('fill', colorForCentrality(n.centrality, maxC));
  circle.setAttribute('stroke', '#333');
  circle.setAttribute('stroke-width', '0.5');
  circle.dataset.id = n.id;
  circle.addEventListener('click', () => selectNode(n.id));
  svg.appendChild(circle);
});

function selectNode(id) {
  const n = nodeById[id];
  document.getElementById('selNode').textContent = id;
  document.getElementById('selCentrality').textContent = n.centrality.toFixed(4);
  if (n.resilience_if_removed === null) {
    document.getElementById('selResilience').textContent = '(too large to precompute -- use live backend)';
  } else {
    const ri = n.resilience_if_removed;
    document.getElementById('selResilience').textContent = ri.toFixed(4) + (ri < 1 ? ' (efficiency drops)' : ' (negligible)');
  }
  svg.querySelectorAll('circle').forEach(c => {
    c.setAttribute('stroke', c.dataset.id === id ? '#D85A30' : '#333');
    c.setAttribute('stroke-width', c.dataset.id === id ? '2' : '0.5');
  });
}

document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('selNode').textContent = 'none';
  document.getElementById('selCentrality').textContent = '-';
  document.getElementById('selResilience').textContent = '-';
  svg.querySelectorAll('circle').forEach(c => {
    c.setAttribute('stroke', '#333');
    c.setAttribute('stroke-width', '0.5');
  });
});
</script>
</body>
</html>
"""


def export_html(gpickle_path, output_html_path, gsd_meters_per_pixel=0.3, k=None):
    """
    Builds the widget data from a real tile and writes a complete,
    standalone HTML file you can open in any browser.
    """
    package = build_widget_data(gpickle_path, gsd_meters_per_pixel=gsd_meters_per_pixel, k=k)

    xs = [n["x"] for n in package["nodes"]]
    ys = [n["y"] for n in package["nodes"]]
    pad = 30
    minx, maxx = (min(xs) - pad, max(xs) + pad) if xs else (0, 500)
    miny, maxy = (min(ys) - pad, max(ys) + pad) if ys else (0, 500)
    viewbox = f"{minx} {miny} {maxx - minx} {maxy - miny}"

    html = HTML_TEMPLATE.replace("VIEWBOX_PLACEHOLDER", viewbox)
    html = html.replace("DATA_PLACEHOLDER", json.dumps(package))

    with open(output_html_path, "w") as f:
        f.write(html)

    print(f"Saved interactive heatmap to: {output_html_path}")
    print(f"  -> {len(package['nodes'])} nodes, "
          f"{'resilience precomputed for all nodes' if package['precomputed_resilience'] else 'resilience NOT precomputed (graph too large, centrality only)'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 export_interactive_heatmap.py <input.gpickle> <output.html>")
        sys.exit(1)

    export_html(sys.argv[1], sys.argv[2])
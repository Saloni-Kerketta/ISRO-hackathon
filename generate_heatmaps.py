"""
generate_heatmaps_batch.py
----------------------------
RUN THIS to generate ALL heatmap outputs (map-style PNG, distance
matrix PNG, interactive HTML) for a SHORT LIST of tiles -- your top
demo candidates from run_batch.py's output, not your entire folder.

For each tile in the list, this creates 3 files in the output folder:
    <filename>_map_heatmap.png
    <filename>_distance_matrix.png
    <filename>_interactive.html

Usage:
    python3 generate_heatmaps_batch.py /path/to/graph_folder /path/to/output_folder file1.gpickle file2.gpickle ...

Example, using your actual top candidates:
    python3 generate_heatmaps_batch.py /path/to/graph_output ./heatmap_outputs \
        653518_graph.gpickle 906809_graph.gpickle 883311_graph.gpickle \
        987728_graph.gpickle 816279_graph.gpickle

If you don't pass filenames, it uses the DEFAULT_CANDIDATES list below
-- edit it to match your own top results from run_batch.py.
"""

import sys
import os
import pickle

from heatmaps import (
    plot_centrality_map,
    plot_centrality_map_from_pixel_nodes,
    plot_distance_matrix_heatmap,
)
from export_interactive_heatmap import export_html


# Edit this to match the top rows from your run_batch.py output, if
# you want to skip typing filenames on the command line every time.
# These are the user's actual top 15 candidates from their real
# 8,548-tile batch run, sorted by most dramatic resilience drop first.
DEFAULT_CANDIDATES = [
    "653518_graph.gpickle",
    "906809_graph.gpickle",
    "883311_graph.gpickle",
    "987728_graph.gpickle",
    "816279_graph.gpickle",
    "702425_graph.gpickle",
    "716091_graph.gpickle",
    "753638_graph.gpickle",
    "261077_graph.gpickle",
    "374583_graph.gpickle",
    "41557_graph.gpickle",
    "640623_graph.gpickle",
    "728843_graph.gpickle",
    "723199_graph.gpickle",
    "200270_graph.gpickle",
]


def generate_for_tile(input_path, output_folder, gsd_meters_per_pixel=0.3):
    """
    Generates all 3 heatmap outputs for one tile. Skips a file
    gracefully (prints a warning, continues to the next) if it's
    missing or fails to load, instead of crashing the whole batch.
    """
    filename = os.path.basename(input_path)
    base_name = os.path.splitext(filename)[0]  # strip .gpickle

    if not os.path.exists(input_path):
        print(f"  SKIPPED (not found): {input_path}")
        return False

    try:
        with open(input_path, "rb") as f:
            G = pickle.load(f)
    except Exception as e:
        print(f"  SKIPPED (failed to load {filename}): {e}")
        return False

    map_png_path = os.path.join(output_folder, f"{base_name}_map_heatmap.png")
    matrix_png_path = os.path.join(output_folder, f"{base_name}_distance_matrix.png")
    html_path = os.path.join(output_folder, f"{base_name}_interactive.html")

    try:
        # Real Phase II tiles use (row, col) pixel-tuple node IDs.
        # Some other graphs (e.g. a toy/test graph) might use plain
        # x/y attributes instead. Auto-detect which kind this is so
        # the right plotting function gets used, rather than assuming.
        sample_node = next(iter(G.nodes()), None)
        is_pixel_tuple_graph = isinstance(sample_node, tuple) and len(sample_node) == 2

        if is_pixel_tuple_graph:
            plot_centrality_map_from_pixel_nodes(
                G, output_path=map_png_path, title=f"{base_name} -- Criticality Heatmap"
            )
        else:
            plot_centrality_map(
                G, output_path=map_png_path, title=f"{base_name} -- Criticality Heatmap"
            )

        plot_distance_matrix_heatmap(
            G, output_path=matrix_png_path, title=f"{base_name} -- Distance Matrix"
        )
        export_html(input_path, html_path, gsd_meters_per_pixel=gsd_meters_per_pixel)
    except Exception as e:
        print(f"  FAILED while generating heatmaps for {filename}: {e}")
        return False

    return True


def generate_batch(graph_folder, output_folder, filenames, gsd_meters_per_pixel=0.3):
    """
    Runs generate_for_tile for every filename in `filenames`, which
    are expected to live inside `graph_folder`. Creates output_folder
    if it doesn't already exist.
    """
    os.makedirs(output_folder, exist_ok=True)

    succeeded = 0
    for i, filename in enumerate(filenames, start=1):
        input_path = os.path.join(graph_folder, filename)
        print(f"[{i}/{len(filenames)}] Processing {filename}...")
        if generate_for_tile(input_path, output_folder, gsd_meters_per_pixel=gsd_meters_per_pixel):
            succeeded += 1

    print()
    print(f"Done. {succeeded}/{len(filenames)} tiles processed successfully.")
    print(f"Output files are in: {output_folder}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 generate_heatmaps_batch.py <graph_folder> <output_folder> [file1.gpickle file2.gpickle ...]")
        print()
        print("If no filenames are given, uses the DEFAULT_CANDIDATES list defined at the top of this script.")
        sys.exit(1)

    graph_folder = sys.argv[1]
    output_folder = sys.argv[2]

    if len(sys.argv) > 3:
        filenames = sys.argv[3:]
    else:
        filenames = DEFAULT_CANDIDATES
        print(f"(No filenames given, using DEFAULT_CANDIDATES list defined in this script)")
        print()

    generate_batch(graph_folder, output_folder, filenames)
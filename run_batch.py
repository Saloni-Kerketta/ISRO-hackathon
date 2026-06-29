"""
run_batch.py
------------
RUN THIS WHEN YOU HAVE MANY .gpickle FILES IN ONE FOLDER.

It loops over every .gpickle file, runs the Phase III pipeline on each
one (quietly -- no giant wall of text), and prints ONE summary table
at the end so you can spot the best demo candidates immediately.

It will NOT try to deeply analyze every single tiny/broken tile --
those get a quick "too_small" or "error" label and are skipped from
the heavy math, so the whole batch runs fast even with hundreds of
files.

Usage:
    python3 run_batch.py /path/to/your/graph_folder

If you don't pass a folder, it defaults to wherever your uploaded
.gpickle files currently are.
"""

import sys
import os
import glob

from run_phase3 import run_phase3_on_tile_quiet, GSD_METERS_PER_PIXEL


def run_batch(folder_path, gsd=GSD_METERS_PER_PIXEL, top_n=5):
    """
    Scans `folder_path` for all .gpickle files, runs the quiet Phase
    III pipeline on each, and returns a list of result dictionaries
    (see run_phase3_on_tile_quiet for the shape of each dict).
    """
    pattern = os.path.join(folder_path, "*.gpickle")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No .gpickle files found in: {folder_path}")
        print("Double-check the folder path is correct.")
        return []

    print(f"Found {len(files)} .gpickle file(s). Processing...")
    print()

    results = []
    for i, filepath in enumerate(files, start=1):
        result = run_phase3_on_tile_quiet(filepath, gsd=gsd, top_n=top_n)
        results.append(result)
        # simple progress indicator so you know it's not frozen on a
        # big batch -- updates every 25 files instead of every single
        # one, to avoid spamming the screen.
        if i % 25 == 0 or i == len(files):
            print(f"  ...processed {i}/{len(files)}")

    return results


def print_summary_table(results):
    """
    Prints a clean, scannable table of all results, sorted so the
    MOST INTERESTING tiles for a demo (well-connected, biggest drop
    in resilience when the top gatekeeper fails) appear first.
    """
    ok_results = [r for r in results if r["status"] == "ok"]
    too_small = [r for r in results if r["status"] == "too_small"]
    errored = [r for r in results if r["status"] == "error"]

    print()
    print("=" * 70)
    print(f"SUMMARY: {len(results)} files total")
    print(f"  -> {len(ok_results)} usable (had a real bottleneck to test)")
    print(f"  -> {len(too_small)} too small/sparse to be interesting")
    print(f"  -> {len(errored)} failed to load")
    print("=" * 70)

    if not ok_results:
        print("\nNo usable tiles found. Every tile was too small, too "
              "sparse, or failed to load. You may need a different "
              "batch of Phase II output.")
        return

    # Best demo candidates: prefer a SINGLE connected component (no
    # confusing pre-existing gaps), AND a reasonable minimum size.
    #
    # IMPORTANT: tiny graphs (e.g. 3-4 nodes) can show a "perfect"
    # worst_resilience of 0.0000, but this is MISLEADING, not
    # impressive. With so few nodes, removing one can isolate another
    # node completely, and Global Efficiency for a graph that small
    # collapses to exactly 0 almost by definition -- it doesn't
    # reflect a realistic, demo-worthy "city falling apart", it's just
    # a tiny graph with nowhere left to route through. A real demo
    # needs a tile big enough that the drop in efficiency reflects
    # actual rerouting through a meaningfully sized network.
    MIN_NODES_FOR_DEMO = 30
    single_component = [
        r for r in ok_results
        if r["n_components"] == 1 and r["n_nodes"] >= MIN_NODES_FOR_DEMO
    ]
    ranked = sorted(single_component, key=lambda r: r["worst_resilience"])

    print(f"\nTOP DEMO CANDIDATES (single connected component, sorted by "
          f"most dramatic resilience drop first):\n")
    print(f"  {'File':<20} {'Nodes':<8} {'Edges':<8} {'Top Gatekeeper':<20} {'Worst Resilience':<16}")
    for r in ranked[:15]:
        gk = str(r["top_gatekeeper"])
        print(f"  {r['file']:<20} {r['n_nodes']:<8} {r['n_edges']:<8} {gk:<20} {r['worst_resilience']:<16.4f}")

    if not ranked:
        print("  (none -- every usable tile had multiple disconnected "
              "pieces. You can still demo on a multi-component tile, "
              "it just means part of the city was already cut off "
              "before any simulated failure.)")

    if errored:
        print(f"\n{len(errored)} file(s) failed to load -- showing first 5:")
        for r in errored[:5]:
            print(f"  {r['file']}: {r['error_message']}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = "graphs"
        print(f"(No folder given, defaulting to: {folder})")
        print()

    results = run_batch(folder)
    print_summary_table(results)
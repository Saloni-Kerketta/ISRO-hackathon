"""
geo_utils.py
------------
PURPOSE (in plain English):
    Phase II's graph stores edge 'weight' as a PIXEL count (how many
    pixel-to-pixel steps the road's traced path took). But the
    Resilience Index, Betweenness Centrality, and the whole demo
    narrative ("average commute time increases by X minutes") only
    make real-world sense in METERS, not pixels.

    This file converts pixel weights into real-world meters using the
    image's resolution (how many meters one pixel represents on the
    ground -- this is called the "Ground Sample Distance" or GSD).

WHERE TO GET THE RESOLUTION NUMBER:
    Every satellite image comes with metadata describing its
    resolution. If you have the original GeoTIFF file, the cleanest
    way is to read it directly with the `rasterio` library:

        import rasterio
        with rasterio.open("your_tile.tif") as src:
            gsd_x = src.res[0]   # meters per pixel, x direction
            gsd_y = src.res[1]   # meters per pixel, y direction

    If you don't have the GeoTIFF (e.g. you only got the .gpickle
    graph, like right now), use the KNOWN resolution of whichever
    satellite/dataset produced this tile:

        Cartosat-3            : ~0.25 - 0.3  meters/pixel
        SpaceNet roads dataset: ~0.3  - 0.5  meters/pixel
        DeepGlobe dataset     : ~0.5         meters/pixel
        Resourcesat LISS-IV   : ~5.8         meters/pixel
        Sentinel-2            : ~10          meters/pixel

    Ask whoever ran Phase I which dataset/satellite produced this
    specific tile, then hardcode that GSD value below.

TWO LEVELS OF ACCURACY:
    1. SIMPLE (fast, slightly approximate): multiply pixel-weight by
       GSD directly. This slightly UNDER-counts road length for
       diagonal/curvy roads, because it assumes every pixel-step moved
       exactly 1 pixel in a straight line.
    2. ACCURATE (slower, exact): re-walk each edge's stored 'path'
       (the list of pixel coordinates) and sum the real geometric
       distance between consecutive points, accounting for diagonal
       steps properly (using Pythagoras: a diagonal step covers
       sqrt(2) times more ground distance than a straight one).

    For a hackathon demo, SIMPLE is almost certainly good enough --
    the difference is usually only a few percent. Use ACCURATE if you
    have time and want to be precise.
"""

import math
import networkx as nx


def convert_weights_simple(G, gsd_meters_per_pixel, weight_key="weight"):
    """
    Quick conversion: multiplies every edge's pixel-weight by the GSD.

    Returns a NEW graph -- does not modify the original. This matters
    because you may want to keep the original pixel-based graph around
    for debugging, and only use the meter-converted copy for
    centrality/resilience calculations.

    Parameters
    ----------
    G : networkx.Graph
        Graph with edge weights in PIXELS (e.g. straight from Phase II,
        before any geo conversion).
    gsd_meters_per_pixel : float
        How many real-world meters one pixel represents.
        e.g. 0.3 for Cartosat-3, 5.8 for LISS-IV.
    weight_key : str
        Name of the edge attribute holding the pixel weight.
        Default "weight" matches what Phase II produces.

    Returns
    -------
    networkx.Graph
        A copy of G where every edge's weight is now in meters.
    """
    G_meters = G.copy()
    for u, v, data in G_meters.edges(data=True):
        pixel_weight = data[weight_key]
        data[weight_key] = pixel_weight * gsd_meters_per_pixel
    return G_meters


def _euclidean_pixel_distance(p1, p2):
    """
    Straight-line distance between two pixel coordinates (row, col).
    Just the Pythagorean theorem: sqrt(dx^2 + dy^2).
    A horizontal/vertical step gives distance 1.0
    A diagonal step gives distance sqrt(2) = ~1.414
    """
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx * dx + dy * dy)


def convert_weights_accurate(G, gsd_meters_per_pixel, weight_key="weight", path_key="path"):
    """
    Precise conversion: re-walks each edge's stored pixel 'path' and
    sums the real geometric distance step by step, instead of just
    trusting the raw pixel-count. This correctly accounts for diagonal
    movement (which covers more ground distance per step than a
    straight horizontal/vertical move).

    Use this when you have time and want the most accurate Resilience
    Index possible. Falls back to the simple method for any edge that
    is missing a 'path' attribute (e.g. a "healed" edge added by the
    Kruskal MST stitching step, which connects two points directly
    rather than tracing pixel-by-pixel).

    Parameters
    ----------
    G : networkx.Graph
        Graph with edge weights in PIXELS and a 'path' attribute on
        each edge (list of (row, col) pixel coordinate tuples).
    gsd_meters_per_pixel : float
        Meters per pixel, see module docstring for typical values.
    weight_key : str
        Edge attribute name for the weight. Default "weight".
    path_key : str
        Edge attribute name for the pixel path list. Default "path".

    Returns
    -------
    networkx.Graph
        A copy of G with weights in real-world meters.
    """
    G_meters = G.copy()
    for u, v, data in G_meters.edges(data=True):
        path = data.get(path_key)

        if not path or len(path) < 2:
            # No path info (e.g. a "healed" edge with no pixel trace) --
            # fall back to the simple multiply-by-GSD approach using
            # whatever pixel weight is already stored.
            pixel_weight = data[weight_key]
            data[weight_key] = pixel_weight * gsd_meters_per_pixel
            continue

        # Walk the path step by step, summing real geometric distance.
        total_pixels = 0.0
        for i in range(len(path) - 1):
            total_pixels += _euclidean_pixel_distance(path[i], path[i + 1])

        data[weight_key] = total_pixels * gsd_meters_per_pixel

    return G_meters


if __name__ == "__main__":
    # Quick manual test using the real tile-64 graph you uploaded.
    # Run with: python3 geo_utils.py
    import pickle

    with open("/mnt/user-data/uploads/64_graph.gpickle", "rb") as f:
        G = pickle.load(f)

    print("BEFORE conversion (pixel weights):")
    for u, v, data in G.edges(data=True):
        print(f"  {u} -- {v}: weight={data['weight']} pixels")

    # Example: pretend this tile came from Cartosat-3 (~0.3 m/pixel)
    gsd = 0.3
    G_simple = convert_weights_simple(G, gsd_meters_per_pixel=gsd)
    G_accurate = convert_weights_accurate(G, gsd_meters_per_pixel=gsd)

    print(f"\nAFTER simple conversion (GSD={gsd} m/pixel):")
    for u, v, data in G_simple.edges(data=True):
        print(f"  {u} -- {v}: weight={data['weight']:.2f} meters")

    print(f"\nAFTER accurate conversion (GSD={gsd} m/pixel):")
    for u, v, data in G_accurate.edges(data=True):
        print(f"  {u} -- {v}: weight={data['weight']:.2f} meters")
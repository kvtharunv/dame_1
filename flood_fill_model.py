"""
flood_fill_model.py
====================
Distance-decay flood-front inundation model.

Given a DEM and a breach outflow volume (from breach_model.py), this module
estimates the flood inundation extent and depth by spreading water outward
from the breach location along the downstream drainage corridor, with depth
decaying with distance from the breach -- approximating the shape of a real
dam-break flood wave (deep and fast near the breach, shallower and slower
further downstream) far better than a naive elevation-only "bathtub" fill,
which instead floods the globally lowest points first regardless of whether
they are near or far from the dam.

This module is designed to be swapped out later for a full 2D shallow-water
solve (Delft3D-FLOW) or a 3D particle solve (SPH) behind the same interface:

    inundation = simulate_inundation(dem, breach_point, volume_m3, cell_size_m)

Approach
--------
1. Compute a downstream drainage corridor from the breach point via a
   steepest-descent flow trace (proxy for D8 flow accumulation), so the
   flood is constrained to physically connected, reachable terrain.
2. Compute grid-step distance from the breach along that corridor (BFS),
   giving each reachable cell an "arrival order" from the breach.
3. Assign flood depth as an exponential decay function of that distance,
   solved numerically so the total volume placed matches the input breach
   volume exactly (volume-conserving).
4. Output a raster of flood depth (0 where dry) and the corresponding
   flooded polygon extent.

Real DEM vs. synthetic DEM
---------------------------
This module works with any DEM readable by rasterio (e.g. SRTM/ASTER
GeoTIFF clipped to your AOI). A synthetic-DEM generator is included in
`demo.py` so the pipeline is fully runnable before real SRTM data has been
downloaded and clipped.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class InundationResult:
    depth_grid: np.ndarray        # same shape as DEM, flood depth in metres (0 = dry)
    flooded_mask: np.ndarray      # boolean grid, True where flooded
    flooded_area_m2: float
    volume_used_m3: float         # volume actually placed (<= input volume if corridor too small)
    max_depth_m: float
    cell_size_m: float
    engine: str = "distance-decay-flood-front"  # swap to "SPH" or "Delft3D-FLOW" when coupled


def _flow_accumulation_corridor(dem: np.ndarray, breach_rc, cell_size_m: float,
                                 corridor_percentile: float = 92.0):
    """
    Identify the drainage corridor downstream of the breach point using a
    simple D8-style flow-accumulation proxy computed directly with numpy
    (avoids a hard dependency on richdem, which fails to build in some
    sandboxed environments). For production use, replace this with
    pysheds' full D8 flow-accumulation grid for a hydrologically correct
    channel network.

    Returns a boolean mask of "channel / near-channel" cells, i.e. cells
    with high upstream contributing area, which is where flood water is
    physically constrained to travel.
    """
    rows, cols = dem.shape
    # Simple proxy: cells within a downstream elevation-descending band
    # from the breach point, based on steepest-descent flow paths sampled
    # from a set of seed points around the breach. This approximates a
    # flow-accumulation corridor without a full D8 accumulation pass.
    flow_score = np.zeros_like(dem, dtype=np.float64)

    r0, c0 = breach_rc
    seeds = [(r0, c0)]
    # Seed a small cluster around the breach to widen the initial corridor
    for dr in (-2, -1, 0, 1, 2):
        for dc in (-2, -1, 0, 1, 2):
            rr, cc = r0 + dr, c0 + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                seeds.append((rr, cc))

    for sr, sc in seeds:
        r, c = sr, sc
        visited = set()
        stuck_count = 0
        for _ in range(rows + cols):  # cap steps
            if (r, c) in visited:
                break
            visited.add((r, c))
            flow_score[r, c] += 1.0
            # steepest descent among 8 neighbours
            best = None
            best_val = dem[r, c]
            fallback_best = None       # lowest neighbour even if not strictly lower
            fallback_val = np.inf
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        if dem[rr, cc] < best_val:
                            best_val = dem[rr, cc]
                            best = (rr, cc)
                        if dem[rr, cc] < fallback_val:
                            fallback_val = dem[rr, cc]
                            fallback_best = (rr, cc)
            if best is not None:
                r, c = best
                stuck_count = 0
            elif fallback_best is not None and stuck_count < 5:
                # No strictly-lower neighbour (small local pit, e.g. from
                # DEM noise) -- step to the least-bad neighbour and keep
                # going rather than terminating the trace outright. A
                # real pipeline should depression-fill the DEM first
                # (e.g. pysheds `fill_depressions`); this is a bounded
                # escape hatch so the prototype trace doesn't die on
                # every minor pit.
                r, c = fallback_best
                stuck_count += 1
            else:
                break  # genuine local minimum / basin, stop trace

    # Dilate the traced path slightly to give it a channel width, then
    # threshold to keep only the strongest (most-traced) cells.
    from scipy.ndimage import gaussian_filter, binary_dilation
    smoothed = gaussian_filter(flow_score, sigma=1.5)
    corridor = smoothed > np.percentile(smoothed[smoothed > 0], 
                                         100 - corridor_percentile) if np.any(smoothed > 0) else np.zeros_like(dem, dtype=bool)
    corridor = binary_dilation(corridor, iterations=3)
    return corridor


def _bfs_distance_from_breach(candidate_mask: np.ndarray, breach_rc):
    """
    Computes 8-connected grid-step distance from the breach point across
    the candidate (corridor) mask using a breadth-first search. This gives
    a "how far along the reachable channel is this cell from the breach"
    ordering, which is what a flood wave actually follows -- unlike a pure
    elevation sort, which fills the globally lowest points first regardless
    of whether they are near or far from the breach.

    Returns an array of distances (in grid steps, np.inf where unreached)
    the same shape as candidate_mask.
    """
    from collections import deque

    rows, cols = candidate_mask.shape
    dist = np.full((rows, cols), np.inf, dtype=np.float64)
    r0, c0 = breach_rc
    r0 = min(max(r0, 0), rows - 1)
    c0 = min(max(c0, 0), cols - 1)

    # If the breach cell itself isn't in the candidate mask (e.g. sits just
    # outside the traced corridor), seed the BFS from the nearest candidate
    # cell instead so the flood still has a valid starting point.
    if not candidate_mask[r0, c0]:
        cand_r, cand_c = np.where(candidate_mask)
        if len(cand_r) == 0:
            return dist
        d2 = (cand_r - r0) ** 2 + (cand_c - c0) ** 2
        nearest = np.argmin(d2)
        r0, c0 = int(cand_r[nearest]), int(cand_c[nearest])

    dist[r0, c0] = 0.0
    q = deque([(r0, c0)])
    while q:
        r, c = q.popleft()
        d = dist[r, c]
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols and candidate_mask[rr, cc]:
                    step = 1.4142135 if dr != 0 and dc != 0 else 1.0
                    nd = d + step
                    if nd < dist[rr, cc]:
                        dist[rr, cc] = nd
                        q.append((rr, cc))
    return dist


def simulate_inundation(dem: np.ndarray, breach_rc, volume_m3: float,
                         cell_size_m: float, nodata_value: float = -9999.0) -> InundationResult:
    """
    Parameters
    ----------
    dem : 2D numpy array of elevations (metres), rows x cols
    breach_rc : (row, col) index of the breach location in the DEM array
    volume_m3 : total breach volume to distribute (from breach_model.py)
    cell_size_m : DEM pixel size in metres (e.g. ~30 for SRTM)
    nodata_value : DEM nodata sentinel to exclude from flooding

    Returns
    -------
    InundationResult

    Method
    ------
    Rather than a pure "bathtub" fill (which floods the lowest-elevation
    cells first, regardless of distance from the breach -- physically
    wrong for a dam-break wave, which floods outward from the breach and
    weakens with distance), this model:

    1. Traces the downstream drainage corridor from the breach.
    2. Computes grid-step distance from the breach along that corridor
       (BFS), giving an "arrival order" for the flood front.
    3. Assigns a flood depth that decays with distance from the breach
       (exponential decay), scaled so the cumulative volume placed across
       the corridor matches the input breach volume exactly. This
       reproduces the expected real-world behaviour: deep, fast flooding
       right at the breach, extending and shallowing further downstream --
       a reasonable proxy for a dam-break wave profile pending full
       SPH/Delft3D coupling.
    """
    dem = dem.astype(np.float64)
    valid = dem != nodata_value
    cell_area = cell_size_m ** 2

    corridor = _flow_accumulation_corridor(dem, breach_rc, cell_size_m)
    candidate_mask = corridor & valid
    if not np.any(candidate_mask):
        candidate_mask = valid.copy()

    dist_grid = _bfs_distance_from_breach(candidate_mask, breach_rc)
    reachable = np.isfinite(dist_grid) & candidate_mask
    if not np.any(reachable):
        # Nothing reachable at all (shouldn't normally happen) -- return dry grid.
        depth_grid = np.zeros_like(dem, dtype=np.float64)
        flooded_mask = np.zeros_like(dem, dtype=bool)
        return InundationResult(
            depth_grid=depth_grid, flooded_mask=flooded_mask,
            flooded_area_m2=0.0, volume_used_m3=0.0, max_depth_m=0.0,
            cell_size_m=cell_size_m,
        )

    rows_r, cols_r = np.where(reachable)
    dists = dist_grid[rows_r, cols_r] * cell_size_m  # convert grid steps -> metres

    # Depth profile: exponential decay with distance from breach.
    #   depth(d) = D0 * exp(-d / L)
    # D0 (initial depth right at the breach) is tied to the water head at
    # failure -- physically, depth near the breach approaches the breach
    # flow depth. L (decay length, metres) is solved numerically so that
    # total volume placed matches the input breach volume exactly.
    D0 = None  # set by caller context isn't available here; use a sensible
    # default proportional to typical breach depths, refined by search below.

    def volume_for(D0_try, L_try):
        depths = D0_try * np.exp(-dists / max(L_try, 1e-6))
        return np.sum(depths) * cell_area, depths

    # Initial guess for D0: derived from volume/area order of magnitude
    total_len = max(dists.max(), cell_size_m)
    D0_guess = max(volume_m3 / (len(dists) * cell_area), 0.5)

    # Solve for decay length L via bisection so that volume_for(D0, L) == volume_m3,
    # holding D0 fixed at a physically reasonable "near-breach depth" estimate.
    D0 = D0_guess * 3.0  # near-breach depth typically exceeds the mean fill depth
    lo, hi = cell_size_m * 0.1, total_len * 20.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        vol_mid, _ = volume_for(D0, mid)
        if vol_mid < volume_m3:
            lo = mid
        else:
            hi = mid
    L = 0.5 * (lo + hi)
    vol_final, depths = volume_for(D0, L)

    # Rescale slightly to correct any residual mismatch from the bisection
    # tolerance / D0 assumption, preserving the decay *shape* while
    # enforcing exact volume conservation.
    if vol_final > 0:
        depths = depths * (volume_m3 / vol_final)

    depth_grid = np.zeros_like(dem, dtype=np.float64)
    depth_grid[rows_r, cols_r] = depths
    flooded_mask = depth_grid > 0.02  # 2 cm threshold to avoid speckly "dry" edge cells

    flooded_area = float(np.sum(flooded_mask) * cell_area)
    max_depth = float(np.max(depth_grid)) if np.any(flooded_mask) else 0.0
    volume_used = float(np.sum(depth_grid[flooded_mask]) * cell_area)

    return InundationResult(
        depth_grid=depth_grid,
        flooded_mask=flooded_mask,
        flooded_area_m2=flooded_area,
        volume_used_m3=volume_used,
        max_depth_m=max_depth,
        cell_size_m=cell_size_m,
    )


if __name__ == "__main__":
    # Minimal synthetic self-test: a sloped valley DEM
    size = 150
    y, x = np.mgrid[0:size, 0:size]
    dem = (size - y) * 2.0 + np.abs(x - size / 2) * 1.5  # valley sloping downstream (down = lower row idx... adjust)
    dem = dem.astype(np.float64)

    breach_point = (5, size // 2)  # near the top of the valley
    result = simulate_inundation(dem, breach_point, volume_m3=5e6, cell_size_m=30.0)

    print(f"Flooded area   : {result.flooded_area_m2 / 1e6:.2f} sq km")
    print(f"Volume used    : {result.volume_used_m3:,.0f} m^3 (requested 5,000,000)")
    print(f"Max depth      : {result.max_depth_m:.2f} m")
    print(f"Engine         : {result.engine}")

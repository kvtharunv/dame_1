"""
breach_model.py
================
Dam / embankment breach hydrograph generator.

Implements the Froehlich (2008) empirical breach model, which is the
industry-standard regression-based method used when a full physically-based
breach-erosion simulation (e.g., coupled with SPH or Delft3D) is not yet
available. This module is designed to be swapped out later for a call into
a real SPH or Delft3D breach-erosion solver without changing its interface:

    breach = compute_breach(dam_params)

`breach` always returns the same structured output (peak discharge, breach
geometry, time-to-failure, and the full outflow hydrograph as a time series)
regardless of which engine produced it.

Reference:
Froehlich, D.C. (2008). "Embankment Dam Breach Parameters and Their
Uncertainties." Journal of Hydraulic Engineering, ASCE, 134(12), 1708-1721.
"""

from dataclasses import dataclass, field
import numpy as np


# ---------------------------------------------------------------------------
# Input / output data structures
# ---------------------------------------------------------------------------

@dataclass
class DamParameters:
    """
    Physical parameters describing the dam / embankment prior to failure.
    All units are SI (metres, cubic metres, seconds) unless noted.
    """
    name: str
    dam_height: float          # height of dam, m (structural height)
    hw_height: float           # height of water above breach invert at failure, m
                                # (often ~ dam_height for a full-reservoir dam-break scenario)
    reservoir_volume: float    # reservoir storage volume at failure, m^3
    failure_mode: str = "overtopping"   # "overtopping" or "piping" (affects Froehlich coefficients)
    downstream_slope_H_to_V: float = 1.4  # average embankment downstream face slope (H:V), typical 1.0-2.0


@dataclass
class BreachResult:
    """Structured output of the breach model, engine-agnostic."""
    dam_name: str
    breach_width_avg: float        # average breach width, m
    breach_side_slope_z: float     # breach side slope (z:1, H:V)
    time_to_failure_hr: float      # time from breach initiation to full formation, hours
    peak_outflow_m3s: float        # peak breach discharge, m^3/s
    time_series_s: np.ndarray      # time array, seconds, from breach start
    outflow_series_m3s: np.ndarray  # discharge hydrograph, m^3/s, aligned with time_series_s
    total_volume_released_m3: float  # sanity-check: integral of hydrograph
    engine: str = "Froehlich2008-empirical"  # swap to "SPH" or "Delft3D" when coupled


# ---------------------------------------------------------------------------
# Froehlich (2008) empirical formulas
# ---------------------------------------------------------------------------

def _froehlich_breach_geometry(dam: DamParameters):
    """
    Returns (breach_width_avg [m], side_slope_z [-], time_to_failure [hours])

    Froehlich (2008) regression equations:
        Bavg = 0.27 * kO * Vw^0.32 * hb^0.04
        tf   = 63.2 * sqrt(Vw / (g * hb^2))
    where:
        Vw  = reservoir volume at time of failure, m^3
        hb  = breach height (~ height of water above breach invert), m
        kO  = 1.3 for overtopping failure, 1.0 for piping failure
        g   = gravitational acceleration, 9.81 m/s^2
    Side slope z (H:V) is taken as 1.0 for overtopping (near-vertical
    erosion) and 0.7-1.4 for piping; we use the common design defaults.
    """
    g = 9.81
    Vw = dam.reservoir_volume
    hb = dam.hw_height

    kO = 1.3 if dam.failure_mode == "overtopping" else 1.0
    z = 1.0 if dam.failure_mode == "overtopping" else 0.9

    Bavg = 0.27 * kO * (Vw ** 0.32) * (hb ** 0.04)
    tf_hours = 63.2 * np.sqrt(Vw / (g * hb ** 2)) / 3600.0

    return Bavg, z, tf_hours


def _peak_breach_outflow(dam: DamParameters, Bavg: float, z: float, tf_hours: float):
    """
    Peak breach outflow using the physically-based weir-breach relation
    commonly paired with Froehlich geometry (as recommended in FERC/USBR
    guidance), treating the breach as a broad-crested/trapezoidal weir at
    the moment of maximum breach development:

        Qp = Cd * [ (Bavg) * hb^1.5  +  (8/15) * z * hb^2.5 * sqrt(2g) ]

    Cd ~ 1.7 (typical broad-crested weir coefficient for earthen breach)
    This is the standard simplification used when a full unsteady breach
    erosion / hydrodynamic solver is not run.
    """
    g = 9.81
    Cd = 1.7
    hb = dam.hw_height
    Qp = Cd * (Bavg * hb ** 1.5 + (8.0 / 15.0) * z * (2 * g) ** 0.5 * hb ** 2.5)
    return Qp


def _build_hydrograph(Qp: float, tf_hours: float, dam: DamParameters,
                       dt_s: float = 30.0):
    """
    Builds a triangular-rise / exponential-recession breach hydrograph, the
    standard shape used in dam-break studies (rapid rise to Qp over the
    breach formation time, followed by exponential recession as the
    reservoir drains).

    - Rising limb: linear from 0 to Qp over tf_hours (breach formation time).
    - Falling limb: exponential decay Q(t) = Qp * exp(-t/tau), tau scaled
      to the breach formation time (tau = 1.5 * tf_s), a standard
      recession shape for embankment breach hydrographs.
    - Physical stopping condition: the hydrograph is truncated at the
      instant the cumulative released volume reaches the reservoir's
      actual storage volume (the reservoir simply empties). This is the
      correct physical constraint -- rather than forcing the empirical
      weir-peak formula to artificially match the reservoir volume, which
      can distort Qp for large dams where the Froehlich/weir peak alone
      would drain the reservoir before the shape naturally recedes.
    """
    tf_s = max(tf_hours * 3600.0, dt_s)
    tau = 1.5 * tf_s

    t_rise = np.arange(0, tf_s, dt_s)
    q_rise = Qp * (t_rise / tf_s)

    t_fall = np.arange(0, tau * 8, dt_s)
    q_fall = Qp * np.exp(-t_fall / tau)

    t_full = np.concatenate([t_rise, tf_s + t_fall])
    q_full = np.concatenate([q_rise, q_fall])

    # Truncate at the point cumulative volume reaches reservoir storage
    cum_vol = np.concatenate([[0.0], np.cumsum(
        0.5 * (q_full[1:] + q_full[:-1]) * np.diff(t_full)
    )])
    if cum_vol[-1] > dam.reservoir_volume:
        cutoff_idx = np.searchsorted(cum_vol, dam.reservoir_volume)
        cutoff_idx = min(max(cutoff_idx, 1), len(t_full) - 1)
        t_full = t_full[:cutoff_idx + 1]
        q_full = q_full[:cutoff_idx + 1]
        # Taper the last point to zero over one extra step so the
        # hydrograph doesn't end on an abrupt discontinuity in plots.
        t_full = np.append(t_full, t_full[-1] + dt_s)
        q_full = np.append(q_full, 0.0)

    return t_full, q_full


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_breach(dam: DamParameters) -> BreachResult:
    """
    Main entry point. Given DamParameters, returns a BreachResult with the
    full outflow hydrograph.

    This function signature is intentionally engine-agnostic: a future
    SPH or Delft3D breach-erosion coupling can replace the internals while
    keeping compute_breach(dam) -> BreachResult stable for the rest of the
    pipeline (dashboard, GIS export, etc.).
    """
    Bavg, z, tf_hours = _froehlich_breach_geometry(dam)
    Qp = _peak_breach_outflow(dam, Bavg, z, tf_hours)
    t_series, q_series = _build_hydrograph(Qp, tf_hours, dam)
    total_vol = float(np.trapezoid(q_series, t_series))

    return BreachResult(
        dam_name=dam.name,
        breach_width_avg=float(Bavg),
        breach_side_slope_z=float(z),
        time_to_failure_hr=float(tf_hours),
        peak_outflow_m3s=float(Qp),
        time_series_s=t_series,
        outflow_series_m3s=q_series,
        total_volume_released_m3=total_vol,
    )


# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example: Subansiri Lower Dam approximate public-domain parameters
    # (design height ~130 m; used here illustratively for a hypothetical
    # dam-break scenario, NOT an actual failure event).
    subansiri = DamParameters(
        name="Subansiri_Lower_Dam_hypothetical",
        dam_height=130.0,
        hw_height=110.0,                # water head above breach invert
        reservoir_volume=1.2e9,         # ~1.2 billion m^3 approx. live storage
        failure_mode="overtopping",
    )

    result = compute_breach(subansiri)

    print(f"Dam: {result.dam_name}")
    print(f"Breach avg width      : {result.breach_width_avg:.1f} m")
    print(f"Breach side slope (z) : {result.breach_side_slope_z:.2f} (H:V)")
    print(f"Time to failure       : {result.time_to_failure_hr:.2f} hours")
    print(f"Peak outflow (Qp)     : {result.peak_outflow_m3s:,.0f} m^3/s")
    print(f"Total volume released : {result.total_volume_released_m3:,.0f} m^3")
    print(f"Engine                : {result.engine}")

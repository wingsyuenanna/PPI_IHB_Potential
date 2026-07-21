# optimize_flatblock_multiband_heatpump.py
# Multi-band heat-pump + IHB optimization (HiGHS), representative-days formulation.
#
# One shared on-site solar array feeds B parallel temperature bands. Each band converts
# electricity to heat via a COP (heat pump COP>1 below 200 C; resistive COP=1 above) and
# charges a thermal store serving a flat load. Converter equipment CAPEX is optional
# (default off when include_converter_cost=False — the HP / heat battery is the converter).
#
# Because storage is ~16 h it CYCLES DAILY (fills by day, drains overnight), so days are
# effectively independent. We therefore cluster the year's 365 daily solar profiles into K
# REPRESENTATIVE DAYS (numpy k-means, medoid profiles), solve each as a self-contained 24-h
# block with its own storage cycle, and weight by cluster frequency. This shrinks the LP
# ~20x vs full 8760-h with negligible accuracy loss for daily-cycling storage.
#
# Reliability: hard floor at availability_factor (e.g. 90%). If land makes that infeasible,
# a two-phase solve maximizes served heat then minimizes solar+storage cost for that level.
# Unserved is NOT costed in LCOH (VoLL may be 0). Each rep-day uses a cyclic SOC so overnight
# load can draw heat stored the previous afternoon. Currency follows input_costs (USD).

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from highspy import Highs, HighsModelStatus

HS_INF = 1e30


def _crf(discount_rate: float, lifetime_years: int) -> float:
    r = float(discount_rate)
    n = int(lifetime_years)
    if n <= 0:
        raise ValueError("lifetime_years must be > 0")
    if r <= 0:
        return 1.0 / n
    return r / (1.0 - (1.0 + r) ** (-n))


def _kmeans(X: np.ndarray, K: int, iters: int = 60, seed: int = 0):
    """Minimal numpy k-means. Returns (labels, centroids)."""
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), K, replace=False)].copy()
    labels = np.full(len(X), -1)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        new = d.argmin(1)
        if np.array_equal(new, labels):
            break
        labels = new
        for k in range(K):
            m = X[labels == k]
            if len(m):
                C[k] = m.mean(0)
    return labels, C


def representative_days(g: np.ndarray, n_rep: int | None, seed: int = 0):
    """Cluster daily solar profiles into representative (medoid) days with weights."""
    days = len(g) // 24
    D = g[: days * 24].reshape(days, 24)
    if n_rep is None or n_rep >= days:
        return D, np.ones(days, dtype=float)
    labels, C = _kmeans(D, n_rep, seed=seed)
    reps, weights = [], []
    for k in range(n_rep):
        members_idx = np.where(labels == k)[0]
        if len(members_idx) == 0:
            continue
        members = D[members_idx]
        medoid = members[np.argmin(((members - C[k]) ** 2).sum(1))]
        reps.append(medoid)
        weights.append(float(len(members_idx)))
    return np.array(reps), np.array(weights, dtype=float)


DEFAULT_COP_BY_BAND = {
    "heat_below100C_tj": 2.7,
    "heat_100C-200C_tj": 1.8,
    "heat_200C-500C_tj": 1.0,
    "heat_500C-1000C_tj": 1.0,
    "heat_above1000C_tj": 1.0,
}
DEFAULT_CONV_CAPEX_THERMAL_BY_BAND = {
    "heat_below100C_tj": 700_000.0,
    "heat_100C-200C_tj": 1_000_000.0,
    "heat_200C-500C_tj": 150_000.0,
    "heat_500C-1000C_tj": 200_000.0,
    "heat_above1000C_tj": 200_000.0,
}
ZERO_CONV_CAPEX_BY_BAND = {b: 0.0 for b in DEFAULT_CONV_CAPEX_THERMAL_BY_BAND}


def run_multiband_heatpump_optimization(
    site_id: int,
    availability_factor: float,
    solar_profile_df: pd.DataFrame,
    input_costs: Dict[str, Any],
    band_loads: Dict[str, float],
    *,
    cop_by_band: Dict[str, float] | None = None,
    conv_capex_thermal_by_band: Dict[str, float] | None = None,
    include_converter_cost: bool = False,
    round_trip_efficiency: float = 0.92,
    max_storage_hours: float = 16.0,
    charge_discharge_ratio_min: float = 4.0,
    inverter_efficiency: float = 0.967,
    conv_lifetime_years: int = 20,
    conv_opex_frac: float = 0.02,
    max_solar_mw: float | None = None,
    VoLL: float = 0.0,
    n_representative_days: int | None = 16,
    project_start_year: int = 2025,
) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame], bool]:
    """Minimize solar (+ optional converter) + storage LCOH over representative days.

    Hard reliability floor at ``availability_factor``. Unserved is not included in LCOH
    (VoLL defaults to 0). Converter CAPEX defaults off — COP still applies to energy.
    """
    cop_by_band = cop_by_band or DEFAULT_COP_BY_BAND
    if not include_converter_cost:
        conv_capex_thermal_by_band = ZERO_CONV_CAPEX_BY_BAND
    else:
        conv_capex_thermal_by_band = conv_capex_thermal_by_band or DEFAULT_CONV_CAPEX_THERMAL_BY_BAND

    fin = input_costs["financial"]
    solar_p = input_costs["solar"]
    batt = input_costs.get("battery", {})
    CRF = fin["CRF"]
    solar_cost_per_mw = (solar_p["Capex"] * 1000.0) * CRF + solar_p["Fixed O&M"]

    capex_kwh = float(batt.get("Thermal CAPEX $/kWh", 20.0))
    opex_frac = float(batt.get("Thermal OPEX frac/yr", 0.01))
    life = int(round(float(batt.get("Thermal Lifetime yr", 20.0))))
    disc = float(batt.get("Thermal Discount rate", 0.08))
    if disc > 1.0:
        disc /= 100.0
    tes_energy_annual_per_mwh = capex_kwh * 1000.0 * (_crf(disc, life) + opex_frac)
    conv_annual_factor = _crf(disc, conv_lifetime_years) + conv_opex_frac

    rte = float(np.clip(round_trip_efficiency, 0.05, 0.999))
    eta = float(np.sqrt(rte))
    inv = float(np.clip(inverter_efficiency, 0.5, 1.0))
    h_max = float(max(0.5, max_storage_hours))
    ratio_cd = float(max(charge_discharge_ratio_min, 1e-6))
    af = float(np.clip(availability_factor, 0.0, 1.0))

    ydf = solar_profile_df[solar_profile_df["year"] == solar_profile_df["year"].iloc[0]]
    g_full = ydf["P_kWperkWp"].to_numpy(dtype=float)
    reps, weights = representative_days(g_full, n_representative_days)
    K, H = reps.shape
    total_days = float(weights.sum())

    bands = [(b, float(load)) for b, load in band_loads.items() if load and load > 0]
    if not bands:
        return None, None, False
    nb = len(bands)
    total_load_MW = sum(load for _, load in bands)
    annual_load_MWh = total_load_MW * total_days * H
    target_unserved_cap = (1.0 - af) * annual_load_MWh

    ix: Dict[tuple, int] = {}
    col = 1
    for b, _ in bands:
        ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")] = col, col + 1, col + 2
        col += 3
    n_cap = col
    band_stride = K * 5 * H

    def hidx(j, c, kind):
        base = n_cap + j * band_stride + c * 5 * H
        # Keep 5 slots for layout compatibility; solar_used unused (charge draws solar directly)
        return base + {"solar_used": 0, "charge": 1, "discharge": 2, "soc": 3, "unserved": 4}[kind] * H

    n_total = n_cap + nb * band_stride
    NINF = -HS_INF

    def _build(objective: str, unserved_cap: float | None) -> Highs:
        """objective: 'cost' | 'unserved'.

        Physics: shared solar → per-band charge (×COP into heat store) → discharge to load.
        No electrical bus loop; charge is the only solar draw.
        """
        cost = np.zeros(n_total, dtype=np.float64)
        lower = np.zeros(n_total, dtype=np.float64)
        upper = np.full(n_total, HS_INF, dtype=np.float64)
        upper[0] = max_solar_mw if (max_solar_mw is not None and max_solar_mw >= 0) else HS_INF
        # solar_used columns unused — freeze at 0
        for j in range(nb):
            for c in range(K):
                su0 = hidx(j, c, "solar_used")
                upper[su0:su0 + H] = 0.0

        if objective == "cost":
            cost[0] = solar_cost_per_mw / annual_load_MWh
            for b, _ in bands:
                cop = cop_by_band.get(b, 1.0)
                conv_annual = conv_capex_thermal_by_band.get(b, 0.0) * cop * conv_annual_factor
                cost[ix[(b, "P_ch")]] = conv_annual / annual_load_MWh
                cost[ix[(b, "E")]] = tes_energy_annual_per_mwh / annual_load_MWh
            if VoLL > 0:
                for j in range(nb):
                    for c in range(K):
                        un0 = hidx(j, c, "unserved")
                        cost[un0:un0 + H] = VoLL * weights[c] / annual_load_MWh
        else:
            for j in range(nb):
                for c in range(K):
                    un0 = hidx(j, c, "unserved")
                    cost[un0:un0 + H] = weights[c]

        h = Highs()
        h.silent()
        h.addCols(n_total, cost, lower, upper, 0,
                  np.zeros(n_total, dtype=np.int32),
                  np.array([], dtype=np.int32), np.array([], dtype=np.float64))

        r_lo, r_hi, r_start, c_idx, c_val = [], [], [], [], []

        def row(lo, hi, cols, coeffs):
            r_start.append(len(c_idx))
            r_lo.append(lo)
            r_hi.append(hi)
            c_idx.extend(cols)
            c_val.extend(coeffs)

        for j, (b, load) in enumerate(bands):
            cop = cop_by_band.get(b, 1.0)
            Pch, Pdis, E = ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")]
            row(NINF, 0, [E, Pdis], [1.0, -h_max])
            row(0, HS_INF, [Pch, Pdis], [1.0, -ratio_cd])
            for c in range(K):
                ch, dis, sc, un = (hidx(j, c, k) for k in
                                  ("charge", "discharge", "soc", "unserved"))
                for t in range(H):
                    # Thermal load balance: discharge + unserved = load
                    row(load, load, [dis + t, un + t], [1.0, 1.0])
                    # Cyclic daily SOC (hour 0 continues from hour 23) so overnight
                    # load can use heat stored the previous afternoon within the day.
                    prev = sc + (H - 1) if t == 0 else sc + t - 1
                    row(0, 0, [sc + t, prev, ch + t, dis + t],
                        [1.0, -1.0, -cop * eta, 1.0 / eta])
                    row(NINF, 0, [sc + t, E], [1.0, -1.0])
                    row(NINF, 0, [ch + t, Pch], [1.0, -1.0])
                    row(NINF, 0, [dis + t, Pdis], [1.0, -1.0])

        # Shared solar: sum of band charge <= S * profile
        for c in range(K):
            for t in range(H):
                cols = [hidx(j, c, "charge") + t for j in range(nb)] + [0]
                row(NINF, 0, cols, [1.0] * nb + [-reps[c, t]])

        if unserved_cap is not None:
            ucols, ucoeffs = [], []
            for j in range(nb):
                for c in range(K):
                    un0 = hidx(j, c, "unserved")
                    for t in range(H):
                        ucols.append(un0 + t)
                        ucoeffs.append(weights[c])
            row(NINF, float(unserved_cap), ucols, ucoeffs)

        h.addRows(len(r_lo), np.array(r_lo, dtype=np.float64), np.array(r_hi, dtype=np.float64),
                  len(c_idx), np.array(r_start, dtype=np.int32),
                  np.array(c_idx, dtype=np.int32), np.array(c_val, dtype=np.float64))
        h.setOptionValue("time_limit", 120.0)
        return h

    def _unserved(cv: np.ndarray) -> float:
        total = 0.0
        for j in range(nb):
            for c in range(K):
                un0 = hidx(j, c, "unserved")
                total += weights[c] * float(cv[un0:un0 + H].sum())
        return total

    t0 = time.time()
    h = _build("cost", target_unserved_cap)
    h.minimize()
    met_availability = h.getModelStatus() == HighsModelStatus.kOptimal
    if not met_availability:
        h1 = _build("unserved", None)
        h1.minimize()
        if h1.getModelStatus() != HighsModelStatus.kOptimal:
            print(f"⚠️ site {site_id}: not optimal ({h1.getModelStatus()})")
            return None, None, False
        u_star = _unserved(np.asarray(h1.getSolution().col_value, dtype=float))
        h = _build("cost", u_star * 1.0001 + 1e-6)
        h.minimize()
        if h.getModelStatus() != HighsModelStatus.kOptimal:
            print(f"⚠️ site {site_id}: cost phase not optimal ({h.getModelStatus()})")
            return None, None, False

    elapsed = time.time() - t0
    cv = np.asarray(h.getSolution().col_value, dtype=float)
    S_opt = float(cv[0])
    annual_solar_cost = solar_cost_per_mw * S_opt
    per_band, total_unserved, annual_conv_cost, annual_tes_cost = {}, 0.0, 0.0, 0.0
    for j, (b, load) in enumerate(bands):
        cop = cop_by_band.get(b, 1.0)
        Pch, Pdis, E = (float(cv[ix[(b, k)]]) for k in ("P_ch", "P_dis", "E"))
        band_unserved = 0.0
        for c in range(K):
            un0 = hidx(j, c, "unserved")
            band_unserved += weights[c] * float(cv[un0:un0 + H].sum())
        total_unserved += band_unserved
        annual_conv_cost += conv_capex_thermal_by_band.get(b, 0.0) * cop * conv_annual_factor * Pch
        annual_tes_cost += tes_energy_annual_per_mwh * E
        per_band[b] = {"load_MW": load, "cop": cop, "P_charge_MW": Pch,
                       "P_discharge_MW": Pdis, "E_TES_MWh": E, "unserved_MWh": band_unserved}

    served_MWh = max(annual_load_MWh - total_unserved, 0.0)
    reliability = served_MWh / annual_load_MWh * 100 if annual_load_MWh > 0 else 0.0
    system_annual = annual_solar_cost + annual_conv_cost + annual_tes_cost
    lcoh_served = system_annual / served_MWh if served_MWh > 0 else np.nan
    den = served_MWh if served_MWh > 0 else np.nan

    results = {
        "site": site_id, "n_bands": nb, "n_rep_days": K, "total_load_MW": total_load_MW,
        "S_opt_MW": S_opt,
        "solar_per_load_MWdc_per_MWth": S_opt / total_load_MW if total_load_MW else np.nan,
        "storage_energy_MWh_total": sum(v["E_TES_MWh"] for v in per_band.values()),
        "LCOH_total_$perMWh": system_annual / annual_load_MWh if annual_load_MWh > 0 else np.nan,
        "LCOH_served_$perMWh": lcoh_served,
        "LCOH_solar_$perMWh": annual_solar_cost / den if den == den else np.nan,
        "LCOH_converter_$perMWh": annual_conv_cost / den if den == den else np.nan,
        "LCOH_storage_$perMWh": annual_tes_cost / den if den == den else np.nan,
        "Reliability_%": reliability, "Unserved_MWh": total_unserved,
        "met_availability_target": bool(met_availability),
        "include_converter_cost": bool(include_converter_cost),
        "hp_load_MW": sum(v["load_MW"] for v in per_band.values() if v["cop"] > 1.0),
        "ihb_load_MW": sum(v["load_MW"] for v in per_band.values() if v["cop"] <= 1.0),
        "solve_seconds": elapsed, "project_start_year": int(project_start_year), "bands": per_band,
    }
    return results, None, True


if __name__ == "__main__":
    print("Multi-band heat-pump + IHB HiGHS optimizer (representative days). "
          "Import and call run_multiband_heatpump_optimization(...).")

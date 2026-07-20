# optimize_flatblock_multiband_heatpump.py
# Multi-band heat-pump + IHB optimization (HiGHS), representative-days formulation.
#
# One shared on-site solar array feeds B parallel temperature bands. Each band has its own
# converter (heat pump for <200 C via COP>1, resistive for >200 C via COP~1), thermal store,
# and flat load. The heat-pump effect is the COP multiplier in the charge->heat conversion:
# 1 MWh of solar electricity becomes COP MWh of stored heat, so low-temperature bands need
# far less solar (and land).
#
# Because storage is ~16 h it CYCLES DAILY (fills by day, drains overnight), so days are
# effectively independent. We therefore cluster the year's 365 daily solar profiles into K
# REPRESENTATIVE DAYS (numpy k-means, medoid profiles), solve each as a self-contained 24-h
# block with its own storage cycle, and weight by cluster frequency. This shrinks the LP
# ~20x vs full 8760-h with negligible accuracy loss for daily-cycling storage.
#
# Base case: P_charge >= 4 x P_discharge (converter crams a day's heat into the ~6 h solar
# window), 16 h storage, flat SOC ceiling (no usable-fraction penalty), all electricity from
# on-site solar (no grid). Currency follows input_costs (USD).

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


def run_multiband_heatpump_optimization(
    site_id: int,
    availability_factor: float,
    solar_profile_df: pd.DataFrame,
    input_costs: Dict[str, Any],
    band_loads: Dict[str, float],
    *,
    cop_by_band: Dict[str, float] | None = None,
    conv_capex_thermal_by_band: Dict[str, float] | None = None,
    round_trip_efficiency: float = 0.92,
    max_storage_hours: float = 16.0,
    charge_discharge_ratio_min: float = 4.0,
    inverter_efficiency: float = 0.967,
    conv_lifetime_years: int = 20,
    conv_opex_frac: float = 0.02,
    max_solar_mw: float | None = None,
    VoLL: float = 2000.0,
    n_representative_days: int | None = 16,
    project_start_year: int = 2025,
) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame], bool]:
    """Minimize LCOH for one shared solar array + per-band heat-pump/resistive + storage,
    over K representative days. band_loads maps a temperature-band name to its flat load
    (MW_th). Unserved is soft (penalized at VoLL) so land-limited sites stay feasible.
    Returns (results, None, ok)."""
    cop_by_band = cop_by_band or DEFAULT_COP_BY_BAND
    conv_capex_thermal_by_band = conv_capex_thermal_by_band or DEFAULT_CONV_CAPEX_THERMAL_BY_BAND

    # ── Costs ───────────────────────────────────────────────────────────────
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

    ydf = solar_profile_df[solar_profile_df["year"] == solar_profile_df["year"].iloc[0]]
    g_full = ydf["P_kWperkWp"].to_numpy(dtype=float)
    reps, weights = representative_days(g_full, n_representative_days)  # reps: (K,24), weights:(K,)
    K, H = reps.shape
    total_days = float(weights.sum())

    bands = [(b, float(load)) for b, load in band_loads.items() if load and load > 0]
    if not bands:
        return None, None, False
    nb = len(bands)
    total_load_MW = sum(load for _, load in bands)
    annual_load_MWh = total_load_MW * total_days * H  # = total_load * 8760

    # ── Variable index map ──────────────────────────────────────────────────
    ix: Dict[tuple, int] = {}
    col = 1
    for b, _ in bands:
        ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")] = col, col + 1, col + 2
        col += 3
    n_cap = col
    band_stride = K * 5 * H

    def hidx(j, c, kind):  # hourly block start for band j, rep-day c
        base = n_cap + j * band_stride + c * 5 * H
        return base + {"solar_used": 0, "charge": 1, "discharge": 2, "soc": 3, "unserved": 4}[kind] * H

    n_total = n_cap + nb * band_stride

    # ── Column costs / bounds ───────────────────────────────────────────────
    cost = np.zeros(n_total, dtype=np.float64)
    lower = np.zeros(n_total, dtype=np.float64)
    upper = np.full(n_total, HS_INF, dtype=np.float64)
    cost[0] = solar_cost_per_mw / annual_load_MWh
    upper[0] = max_solar_mw if (max_solar_mw and max_solar_mw > 0) else HS_INF
    for j, (b, _) in enumerate(bands):
        cop = cop_by_band.get(b, 1.0)
        conv_annual_per_mw_elec = conv_capex_thermal_by_band.get(b, 200_000.0) * cop * conv_annual_factor
        cost[ix[(b, "P_ch")]] = conv_annual_per_mw_elec / annual_load_MWh
        cost[ix[(b, "E")]] = tes_energy_annual_per_mwh / annual_load_MWh
        for c in range(K):
            un0 = hidx(j, c, "unserved")
            cost[un0:un0 + H] = VoLL * weights[c] / annual_load_MWh  # weighted by cluster freq

    h = Highs()
    h.silent()
    h.addCols(n_total, cost, lower, upper, 0,
              np.zeros(n_total, dtype=np.int32), np.array([], dtype=np.int32), np.array([], dtype=np.float64))

    # ── Constraints (batched) ───────────────────────────────────────────────
    r_lo, r_hi, r_start, c_idx, c_val = [], [], [], [], []

    def row(lo, hi, cols, coeffs):
        r_start.append(len(c_idx))
        r_lo.append(lo); r_hi.append(hi)
        c_idx.extend(cols); c_val.extend(coeffs)

    NINF = -HS_INF
    for j, (b, load) in enumerate(bands):
        cop = cop_by_band.get(b, 1.0)
        Pch, Pdis, E = ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")]
        row(NINF, 0, [E, Pdis], [1.0, -h_max])            # duration
        row(0, HS_INF, [Pch, Pdis], [1.0, -ratio_cd])      # charge:discharge ratio
        for c in range(K):
            su, ch, dis, sc, un = (hidx(j, c, k) for k in ("solar_used", "charge", "discharge", "soc", "unserved"))
            for t in range(H):  # each rep-day is an independent 24-h storage cycle
                row(load, load, [su + t, ch + t, dis + t, un + t], [inv, -inv, inv, 1.0])
                if t == 0:
                    row(0, 0, [sc + t, ch + t, dis + t], [1.0, -cop * eta, 1.0 / eta])
                else:
                    row(0, 0, [sc + t, sc + t - 1, ch + t, dis + t], [1.0, -1.0, -cop * eta, 1.0 / eta])
                row(NINF, 0, [sc + t, E], [1.0, -1.0])
                row(NINF, 0, [ch + t, Pch], [1.0, -1.0])
                row(NINF, 0, [dis + t, Pdis], [1.0, -1.0])

    for c in range(K):  # shared solar coupling per rep-day/hour
        for t in range(H):
            cols = [hidx(j, c, "solar_used") + t for j in range(nb)] + [0]
            row(NINF, 0, cols, [1.0] * nb + [-reps[c, t]])

    h.addRows(len(r_lo), np.array(r_lo, dtype=np.float64), np.array(r_hi, dtype=np.float64),
              len(c_idx), np.array(r_start, dtype=np.int32),
              np.array(c_idx, dtype=np.int32), np.array(c_val, dtype=np.float64))

    # ── Solve ───────────────────────────────────────────────────────────────
    h.setOptionValue("time_limit", 120.0)
    t0 = time.time()
    h.minimize()
    elapsed = time.time() - t0
    if h.getModelStatus() != HighsModelStatus.kOptimal:
        print(f"⚠️ site {site_id}: not optimal ({h.getModelStatus()})")
        return None, None, False

    # ── Extract ─────────────────────────────────────────────────────────────
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
        annual_conv_cost += conv_capex_thermal_by_band.get(b, 200_000.0) * cop * conv_annual_factor * Pch
        annual_tes_cost += tes_energy_annual_per_mwh * E
        per_band[b] = {"load_MW": load, "cop": cop, "P_charge_MW": Pch,
                       "P_discharge_MW": Pdis, "E_TES_MWh": E, "unserved_MWh": band_unserved}

    served_MWh = annual_load_MWh - total_unserved
    reliability = served_MWh / annual_load_MWh * 100
    lcoh_served = (annual_solar_cost + annual_conv_cost + annual_tes_cost) / served_MWh if served_MWh > 0 else np.nan

    results = {
        "site": site_id, "n_bands": nb, "n_rep_days": K, "total_load_MW": total_load_MW,
        "S_opt_MW": S_opt, "solar_per_load_MWdc_per_MWth": S_opt / total_load_MW if total_load_MW else np.nan,
        "storage_energy_MWh_total": sum(v["E_TES_MWh"] for v in per_band.values()),
        "LCOH_total_$perMWh": (annual_solar_cost + annual_conv_cost + annual_tes_cost + total_unserved * VoLL) / annual_load_MWh,
        "LCOH_served_$perMWh": lcoh_served,
        "LCOH_solar_$perMWh": annual_solar_cost / annual_load_MWh,
        "LCOH_converter_$perMWh": annual_conv_cost / annual_load_MWh,
        "LCOH_storage_$perMWh": annual_tes_cost / annual_load_MWh,
        "Reliability_%": reliability, "Unserved_MWh": total_unserved,
        "hp_load_MW": sum(v["load_MW"] for v in per_band.values() if v["cop"] > 1.0),
        "ihb_load_MW": sum(v["load_MW"] for v in per_band.values() if v["cop"] <= 1.0),
        "solve_seconds": elapsed, "project_start_year": int(project_start_year), "bands": per_band,
    }
    return results, None, True


if __name__ == "__main__":
    print("Multi-band heat-pump + IHB HiGHS optimizer (representative days). "
          "Import and call run_multiband_heatpump_optimization(...).")

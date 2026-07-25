# optimize_flatblock_multiband_heatpump.py
# Multi-band heat-pump + IHB optimization (HiGHS), representative-days formulation.
#
# One shared on-site solar array feeds two technology chains by temperature:
#   • <200 °C — heat pump powered by solar and/or a shared Li-ion battery
#     (electric storage; BNEF utility-scale 4h costs, implied $/kWh = CAPEX/4)
#   • ≥200 °C — industrial heat battery (resistive charge → thermal store)
#     with Energy Innovation CAPEX: $100/kW-in, $300/kW-out, $5/kWh, RTE 95%;
#     annualized with the same country BNEF CRF as solar / Li-ion
#
# Because storage cycles daily, the year of solar is reduced to K representative days
# (k-means medoids), each solved as a 24-h block with cyclic SOC.
#
# Reliability: hard floor at availability_factor. Land-limited sites: max-serve then
# cost-min. Unserved is not costed in LCOH (VoLL may be 0). Industrial HP and IHB
# CAPEX/FOM are inflated to project-start USD (COST_YEAR_INFLATION.md), then
# annualized at country BNEF CRF. Solar/Li-ion already enter as BNEF project-year $.

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from highspy import Highs, HighsModelStatus

HS_INF = 1e30

DEFAULT_COP_BY_BAND = {
    "heat_below100C_tj": 2.7,
    "heat_100C-200C_tj": 1.8,
    "heat_200C-500C_tj": 1.0,
    "heat_500C-1000C_tj": 1.0,
    "heat_above1000C_tj": 1.0,
}


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


def run_multiband_heatpump_optimization(
    site_id: int,
    availability_factor: float,
    solar_profile_df: pd.DataFrame,
    input_costs: Dict[str, Any],
    band_loads: Dict[str, float],
    *,
    cop_by_band: Dict[str, float] | None = None,
    round_trip_efficiency: float = 0.90,
    max_storage_hours: float = 16.0,
    inverter_efficiency: float = 0.967,
    max_solar_mw: float | None = None,
    VoLL: float = 0.0,
    n_representative_days: int | None = 16,
    project_start_year: int = 2025,
    diurnal_shape_24: np.ndarray | None = None,
    return_hourly: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame], bool]:
    """Minimize solar + Li-ion + IHB LCOH over representative days.

    HP bands (COP>1): solar and/or Li-ion → heat pump → process heat (no thermal store).
    IHB bands (COP≤1): solar → resistive charge → thermal store → process heat.

    If ``return_hourly``, the second return value is a DataFrame of hourly dispatch
    on each representative day (MW electrical or thermal as labeled).
    """
    del inverter_efficiency  # reserved; charge draws solar MWac-equivalent directly
    cop_by_band = cop_by_band or DEFAULT_COP_BY_BAND

    fin = input_costs["financial"]
    solar_p = input_costs["solar"]
    batt = input_costs.get("battery", {})
    CRF = float(fin["CRF"])
    solar_cost_per_mw = (solar_p["Capex"] * 1000.0) * CRF + solar_p["Fixed O&M"]

    # Li-ion (BNEF): cost energy at implied $/kWh from 4h system; FOM on discharge power.
    li_capex_kwh = float(batt.get("Li-ion CAPEX $/kWh", batt.get("Li-ion CAPEX $/kW", 800.0) / 4.0))
    li_fom_per_mw = float(batt.get("Li-ion Fixed O&M $/MW-yr", batt.get("Fixed O&M", 0.0)))
    li_rte = float(np.clip(round_trip_efficiency, 0.05, 0.999))
    li_eta = float(np.sqrt(li_rte))
    li_energy_annual_per_mwh = li_capex_kwh * 1000.0 * CRF
    # FOM charged on discharge power rating (MW)
    li_power_annual_per_mw = li_fom_per_mw

    # IHB — Energy Innovation CAPEX inflated to project-start USD (COST_YEAR_INFLATION.md);
    # finance with country BNEF CRF
    ihb_in_kw = float(batt.get("IHB input CAPEX $/kW", 116.66))
    ihb_out_kw = float(batt.get("IHB delivery CAPEX $/kW", 349.99))
    ihb_kwh = float(batt.get("IHB storage CAPEX $/kWh", 5.83))
    ihb_opex = float(batt.get("IHB OPEX frac/yr", 0.0))
    ihb_rte = float(np.clip(float(batt.get("IHB RTE", 0.95)), 0.05, 0.999))
    ihb_eta = float(np.sqrt(ihb_rte))
    ihb_ann_frac = CRF + ihb_opex  # same country CRF as solar / Li-ion (not EI's 14%)
    ihb_in_annual_per_mw = ihb_in_kw * 1000.0 * ihb_ann_frac
    ihb_out_annual_per_mw = ihb_out_kw * 1000.0 * ihb_ann_frac
    ihb_e_annual_per_mwh = ihb_kwh * 1000.0 * ihb_ann_frac

    # Industrial HP — CAPEX on thermal capacity (flat band load MW_th).
    # CAPEX/FOM are project-start USD (2021 source inflated; see COST_YEAR_INFLATION.md);
    # annualized with country BNEF CRF.
    hp_capex_lt = float(batt.get("HP CAPEX below100C $/kWth", 918.30))
    hp_capex_mt = float(batt.get("HP CAPEX 100C-200C $/kWth", 1141.31))
    hp_fom_lt = float(batt.get("HP FOM below100C $/kWth/yr", 15.74))
    hp_fom_mt = float(batt.get("HP FOM 100C-200C $/kWth/yr", 23.61))
    hp_vom = float(batt.get("HP VOM $/MWhth", 0.0))
    # $/MW_th-yr = CAPEX[$/kW]*1000*CRF + FOM[$/kW-yr]*1000
    hp_lt_annual_per_mw = hp_capex_lt * 1000.0 * CRF + hp_fom_lt * 1000.0
    hp_mt_annual_per_mw = hp_capex_mt * 1000.0 * CRF + hp_fom_mt * 1000.0
    HP_ANNUAL_BY_BAND = {
        "heat_below100C_tj": hp_lt_annual_per_mw,
        "heat_100C-200C_tj": hp_mt_annual_per_mw,
    }

    h_max = float(max(0.5, max_storage_hours))
    af = float(np.clip(availability_factor, 0.0, 1.0))

    ydf = solar_profile_df[solar_profile_df["year"] == solar_profile_df["year"].iloc[0]]
    g_full = ydf["P_kWperkWp"].to_numpy(dtype=float)
    reps, weights = representative_days(g_full, n_representative_days)
    K, H = reps.shape
    total_days = float(weights.sum())
    if diurnal_shape_24 is None:
        shape24 = np.ones(H, dtype=float)
    else:
        shape24 = np.asarray(diurnal_shape_24, dtype=float).reshape(-1)
        if len(shape24) != H:
            raise ValueError(f"diurnal_shape_24 must have length {H}, got {len(shape24)}")
        mu = float(shape24.mean())
        if mu <= 0:
            raise ValueError("diurnal_shape_24 mean must be > 0")
        shape24 = shape24 / mu

    bands: List[Tuple[str, float, float]] = []
    for b, load in band_loads.items():
        load_f = float(load)
        if load_f <= 0:
            continue
        bands.append((b, load_f, float(cop_by_band.get(b, 1.0))))
    if not bands:
        return None, None, False

    hp_idx = [i for i, (_, _, cop) in enumerate(bands) if cop > 1.0]
    ihb_idx = [i for i, (_, _, cop) in enumerate(bands) if cop <= 1.0]
    nb = len(bands)
    n_hp = len(hp_idx)
    n_ihb = len(ihb_idx)
    total_load_MW = sum(load for _, load, _ in bands)
    annual_load_MWh = total_load_MW * total_days * H
    target_unserved_cap = (1.0 - af) * annual_load_MWh

    # ---- Column layout ----
    # 0: S
    # Li-ion caps (if any HP band): P_ch, P_dis, E
    # Per IHB band caps: P_ch, P_dis, E
    # Hourly blocks follow.
    col = 1
    li_Pch = li_Pdis = li_E = None
    if n_hp:
        li_Pch, li_Pdis, li_E = col, col + 1, col + 2
        col += 3

    ihb_cap: Dict[int, Tuple[int, int, int]] = {}
    for j in ihb_idx:
        ihb_cap[j] = (col, col + 1, col + 2)
        col += 3
    n_cap = col

    # Hourly: for each rep-day c
    #   Li-ion (if HP): charge, discharge, soc  (3H) + per HP band: direct_e, from_batt, unserved (3H each)
    #   Per IHB band: charge, discharge, soc, unserved (4H)
    def li_hour_base(c: int) -> int:
        return n_cap + c * _day_stride

    # Precompute day stride
    hp_hourly_per_day = (3 + 3 * n_hp) if n_hp else 0  # li soc trio + per-band
    ihb_hourly_per_day = 4 * n_ihb
    _day_stride = H * (hp_hourly_per_day + ihb_hourly_per_day)

    def li_ch0(c):
        return li_hour_base(c)

    def li_dis0(c):
        return li_hour_base(c) + H

    def li_soc0(c):
        return li_hour_base(c) + 2 * H

    def hp_direct0(j_pos, c):
        # j_pos = position in hp_idx list
        return li_hour_base(c) + 3 * H + j_pos * 3 * H

    def hp_from_batt0(j_pos, c):
        return hp_direct0(j_pos, c) + H

    def hp_un0(j_pos, c):
        return hp_direct0(j_pos, c) + 2 * H

    def ihb_block0(i_pos, c):
        return li_hour_base(c) + H * hp_hourly_per_day + i_pos * 4 * H

    def ihb_ch0(i_pos, c):
        return ihb_block0(i_pos, c)

    def ihb_dis0(i_pos, c):
        return ihb_block0(i_pos, c) + H

    def ihb_soc0(i_pos, c):
        return ihb_block0(i_pos, c) + 2 * H

    def ihb_un0(i_pos, c):
        return ihb_block0(i_pos, c) + 3 * H

    n_total = n_cap + K * _day_stride
    NINF = -HS_INF
    hp_pos = {j: p for p, j in enumerate(hp_idx)}
    ihb_pos = {j: p for p, j in enumerate(ihb_idx)}

    def _build(objective: str, unserved_cap: float | None) -> Highs:
        cost = np.zeros(n_total, dtype=np.float64)
        lower = np.zeros(n_total, dtype=np.float64)
        upper = np.full(n_total, HS_INF, dtype=np.float64)
        upper[0] = max_solar_mw if (max_solar_mw is not None and max_solar_mw >= 0) else HS_INF

        if objective == "cost":
            cost[0] = solar_cost_per_mw / annual_load_MWh
            if n_hp:
                cost[li_E] = li_energy_annual_per_mwh / annual_load_MWh
                cost[li_Pdis] = li_power_annual_per_mw / annual_load_MWh
            for j in ihb_idx:
                Pch, Pdis, E = ihb_cap[j]
                cost[Pch] = ihb_in_annual_per_mw / annual_load_MWh
                cost[Pdis] = ihb_out_annual_per_mw / annual_load_MWh
                cost[E] = ihb_e_annual_per_mwh / annual_load_MWh
            if VoLL > 0:
                for c in range(K):
                    w = weights[c] / annual_load_MWh
                    for p in range(n_hp):
                        u0 = hp_un0(p, c)
                        cost[u0:u0 + H] = VoLL * w
                    for p in range(n_ihb):
                        u0 = ihb_un0(p, c)
                        cost[u0:u0 + H] = VoLL * w
        else:
            for c in range(K):
                for p in range(n_hp):
                    u0 = hp_un0(p, c)
                    cost[u0:u0 + H] = weights[c]
                for p in range(n_ihb):
                    u0 = ihb_un0(p, c)
                    cost[u0:u0 + H] = weights[c]

        h = Highs()
        h.silent()
        h.addCols(
            n_total,
            cost,
            lower,
            upper,
            0,
            np.zeros(n_total, dtype=np.int32),
            np.array([], dtype=np.int32),
            np.array([], dtype=np.float64),
        )

        r_lo, r_hi, r_start, c_idx, c_val = [], [], [], [], []

        def row(lo, hi, cols, coeffs):
            r_start.append(len(c_idx))
            r_lo.append(lo)
            r_hi.append(hi)
            c_idx.extend(cols)
            c_val.extend(coeffs)

        # Energy duration caps: E <= h_max * P_dis
        if n_hp:
            row(NINF, 0, [li_E, li_Pdis], [1.0, -h_max])
        for j in ihb_idx:
            _Pch, _Pdis, _E = ihb_cap[j]
            row(NINF, 0, [_E, _Pdis], [1.0, -h_max])

        for c in range(K):
            # Shared solar: HP direct + Li charge + IHB charge <= S * cf
            for t in range(H):
                cols = [0]
                coeffs = [-reps[c, t]]
                if n_hp:
                    cols.append(li_ch0(c) + t)
                    coeffs.append(1.0)
                    for p in range(n_hp):
                        cols.append(hp_direct0(p, c) + t)
                        coeffs.append(1.0)
                for p in range(n_ihb):
                    cols.append(ihb_ch0(p, c) + t)
                    coeffs.append(1.0)
                row(NINF, 0, cols, coeffs)

            # Li-ion SOC / ratings
            if n_hp:
                ch0, dis0, sc0 = li_ch0(c), li_dis0(c), li_soc0(c)
                for t in range(H):
                    prev = sc0 + (H - 1) if t == 0 else sc0 + t - 1
                    row(
                        0,
                        0,
                        [sc0 + t, prev, ch0 + t, dis0 + t],
                        [1.0, -1.0, -li_eta, 1.0 / li_eta],
                    )
                    row(NINF, 0, [sc0 + t, li_E], [1.0, -1.0])
                    row(NINF, 0, [ch0 + t, li_Pch], [1.0, -1.0])
                    row(NINF, 0, [dis0 + t, li_Pdis], [1.0, -1.0])
                # Li discharge allocation to HP bands
                for t in range(H):
                    cols = [dis0 + t] + [hp_from_batt0(p, c) + t for p in range(n_hp)]
                    coeffs = [1.0] + [-1.0] * n_hp
                    row(0, 0, cols, coeffs)

            # HP band balances: (direct + from_batt) * COP + unserved = load
            for j in hp_idx:
                p = hp_pos[j]
                _, load, cop = bands[j]
                for t in range(H):
                    load_t = load * float(shape24[t])
                    row(
                        load_t,
                        load_t,
                        [
                            hp_direct0(p, c) + t,
                            hp_from_batt0(p, c) + t,
                            hp_un0(p, c) + t,
                        ],
                        [cop, cop, 1.0],
                    )

            # IHB bands: thermal store
            for j in ihb_idx:
                p = ihb_pos[j]
                _, load, cop = bands[j]
                Pch, Pdis, E = ihb_cap[j]
                ch0, dis0, sc0, un0 = (
                    ihb_ch0(p, c),
                    ihb_dis0(p, c),
                    ihb_soc0(p, c),
                    ihb_un0(p, c),
                )
                for t in range(H):
                    load_t = load * float(shape24[t])
                    row(load_t, load_t, [dis0 + t, un0 + t], [1.0, 1.0])
                    prev = sc0 + (H - 1) if t == 0 else sc0 + t - 1
                    row(
                        0,
                        0,
                        [sc0 + t, prev, ch0 + t, dis0 + t],
                        [1.0, -1.0, -cop * ihb_eta, 1.0 / ihb_eta],
                    )
                    row(NINF, 0, [sc0 + t, E], [1.0, -1.0])
                    row(NINF, 0, [ch0 + t, Pch], [1.0, -1.0])
                    row(NINF, 0, [dis0 + t, Pdis], [1.0, -1.0])

        if unserved_cap is not None:
            ucols, ucoeffs = [], []
            for c in range(K):
                for p in range(n_hp):
                    u0 = hp_un0(p, c)
                    for t in range(H):
                        ucols.append(u0 + t)
                        ucoeffs.append(weights[c])
                for p in range(n_ihb):
                    u0 = ihb_un0(p, c)
                    for t in range(H):
                        ucols.append(u0 + t)
                        ucoeffs.append(weights[c])
            row(NINF, float(unserved_cap), ucols, ucoeffs)

        h.addRows(
            len(r_lo),
            np.array(r_lo, dtype=np.float64),
            np.array(r_hi, dtype=np.float64),
            len(c_idx),
            np.array(r_start, dtype=np.int32),
            np.array(c_idx, dtype=np.int32),
            np.array(c_val, dtype=np.float64),
        )
        # Scale with horizon: 16-day runs stay ~2 min; full-year (~365 days) needs
        # much longer or HiGHS hits time_limit and falsely falls into the max-serve path.
        time_limit = float(max(120.0, min(2400.0, 4.0 * K)))
        h.setOptionValue("time_limit", time_limit)
        return h

    def _unserved(cv: np.ndarray) -> float:
        total = 0.0
        for c in range(K):
            for p in range(n_hp):
                u0 = hp_un0(p, c)
                total += weights[c] * float(cv[u0:u0 + H].sum())
            for p in range(n_ihb):
                u0 = ihb_un0(p, c)
                total += weights[c] * float(cv[u0:u0 + H].sum())
        return total

    def _accept_status(status: HighsModelStatus) -> bool:
        """Optimal, or time/iteration limit with a usable primal solution."""
        return status in (
            HighsModelStatus.kOptimal,
            HighsModelStatus.kTimeLimit,
            HighsModelStatus.kIterationLimit,
        )

    t0 = time.time()
    h = _build("cost", target_unserved_cap)
    h.minimize()
    status0 = h.getModelStatus()
    # Only treat true infeasibility as "cannot meet 90%"; timeouts must not
    # flip sites into the land-capped max-serve path.
    met_availability = status0 == HighsModelStatus.kOptimal
    if status0 == HighsModelStatus.kInfeasible:
        h1 = _build("unserved", None)
        h1.minimize()
        if not _accept_status(h1.getModelStatus()):
            print(f"⚠️ site {site_id}: not optimal ({h1.getModelStatus()})")
            return None, None, False
        u_star = _unserved(np.asarray(h1.getSolution().col_value, dtype=float))
        h = _build("cost", u_star * 1.0001 + 1e-6)
        h.minimize()
        if not _accept_status(h.getModelStatus()):
            print(f"⚠️ site {site_id}: cost phase not optimal ({h.getModelStatus()})")
            return None, None, False
    elif not _accept_status(status0):
        print(f"⚠️ site {site_id}: cost@90% not optimal ({status0})")
        return None, None, False
    elif status0 != HighsModelStatus.kOptimal:
        # Time/iteration limit but feasible: keep solution; mark met only if
        # achieved unserved still clears the 90% floor.
        cv_try = np.asarray(h.getSolution().col_value, dtype=float)
        met_availability = _unserved(cv_try) <= target_unserved_cap * 1.0001 + 1e-6

    elapsed = time.time() - t0
    cv = np.asarray(h.getSolution().col_value, dtype=float)
    S_opt = float(cv[0])
    annual_solar_cost = solar_cost_per_mw * S_opt

    annual_li_cost = 0.0
    li_E_mwh = li_P_mw = 0.0
    if n_hp:
        li_E_mwh = float(cv[li_E])
        li_P_mw = float(cv[li_Pdis])
        annual_li_cost = li_energy_annual_per_mwh * li_E_mwh + li_power_annual_per_mw * li_P_mw

    annual_ihb_cost = 0.0
    ihb_E_total = 0.0
    per_band: Dict[str, Any] = {}
    total_unserved = 0.0

    for j, (b, load, cop) in enumerate(bands):
        band_unserved = 0.0
        if j in hp_pos:
            p = hp_pos[j]
            for c in range(K):
                u0 = hp_un0(p, c)
                band_unserved += weights[c] * float(cv[u0:u0 + H].sum())
            per_band[b] = {
                "load_MW": load,
                "cop": cop,
                "storage": "li-ion",
                "P_charge_MW": float(cv[li_Pch]) if n_hp else 0.0,
                "P_discharge_MW": float(cv[li_Pdis]) if n_hp else 0.0,
                "E_storage_MWh": float(cv[li_E]) if n_hp else 0.0,
                "unserved_MWh": band_unserved,
            }
        else:
            p = ihb_pos[j]
            Pch_i, Pdis_i, E_i = ihb_cap[j]
            Pch, Pdis, E = float(cv[Pch_i]), float(cv[Pdis_i]), float(cv[E_i])
            annual_ihb_cost += (
                ihb_in_annual_per_mw * Pch
                + ihb_out_annual_per_mw * Pdis
                + ihb_e_annual_per_mwh * E
            )
            ihb_E_total += E
            for c in range(K):
                u0 = ihb_un0(p, c)
                band_unserved += weights[c] * float(cv[u0:u0 + H].sum())
            per_band[b] = {
                "load_MW": load,
                "cop": cop,
                "storage": "ihb",
                "P_charge_MW": Pch,
                "P_discharge_MW": Pdis,
                "E_storage_MWh": E,
                "unserved_MWh": band_unserved,
            }
        total_unserved += band_unserved

    # HP thermal capacity sized to served heat (not full demand) so land-capped
    # near-zero-serve sites do not get charged full HP CAPEX / tiny served MWh.
    annual_hp_capex_fom = 0.0
    hp_capacity_total = 0.0
    for j, (b, load, cop) in enumerate(bands):
        if cop <= 1.0 or b not in per_band:
            continue
        band_demand_MWh = load * total_days * H
        band_served_MWh = max(band_demand_MWh - float(per_band[b]["unserved_MWh"]), 0.0)
        band_cap_mw = band_served_MWh / (total_days * H) if total_days * H > 0 else 0.0
        hp_capacity_total += band_cap_mw
        annual_hp_capex_fom += band_cap_mw * float(HP_ANNUAL_BY_BAND.get(b, hp_mt_annual_per_mw))

    served_MWh = max(annual_load_MWh - total_unserved, 0.0)
    hp_load_total = sum(load for _, load, cop in bands if cop > 1.0)
    hp_demand_MWh = hp_load_total * total_days * H
    hp_unserved = sum(
        float(per_band[b]["unserved_MWh"])
        for b, load, cop in bands
        if cop > 1.0 and b in per_band
    )
    hp_served_MWh = max(hp_demand_MWh - hp_unserved, 0.0)
    annual_hp_vom = hp_vom * hp_served_MWh
    annual_hp_cost = annual_hp_capex_fom + annual_hp_vom

    reliability = served_MWh / annual_load_MWh * 100 if annual_load_MWh > 0 else 0.0
    storage_annual = annual_li_cost + annual_ihb_cost
    system_annual = annual_solar_cost + storage_annual + annual_hp_cost
    lcoh_served = system_annual / served_MWh if served_MWh > 1e-9 else np.nan
    den = served_MWh if served_MWh > 1e-9 else np.nan

    results = {
        "site": site_id,
        "n_bands": nb,
        "n_rep_days": K,
        "total_load_MW": total_load_MW,
        "S_opt_MW": S_opt,
        "solar_per_load_MWdc_per_MWth": S_opt / total_load_MW if total_load_MW else np.nan,
        "storage_energy_MWh_total": li_E_mwh + ihb_E_total,
        "liion_energy_MWh": li_E_mwh,
        "liion_power_MW": li_P_mw,
        "ihb_energy_MWh": ihb_E_total,
        "hp_capacity_MW_th": hp_capacity_total,
        "LCOH_total_$perMWh": system_annual / annual_load_MWh if annual_load_MWh > 0 else np.nan,
        "LCOH_served_$perMWh": lcoh_served,
        "LCOH_solar_$perMWh": annual_solar_cost / den if den == den else np.nan,
        "LCOH_storage_$perMWh": storage_annual / den if den == den else np.nan,
        "LCOH_liion_$perMWh": annual_li_cost / den if den == den else np.nan,
        "LCOH_ihb_$perMWh": annual_ihb_cost / den if den == den else np.nan,
        "LCOH_hp_$perMWh": annual_hp_cost / den if den == den else np.nan,
        "Reliability_%": reliability,
        "Unserved_MWh": total_unserved,
        "met_availability_target": bool(met_availability),
        "hp_load_MW": hp_load_total,
        "ihb_load_MW": sum(load for _, load, cop in bands if cop <= 1.0),
        "solve_seconds": elapsed,
        "project_start_year": int(project_start_year),
        "bands": per_band,
    }

    hourly_df = None
    if return_hourly:
        rows = []
        for c in range(K):
            solar_mw = S_opt * reps[c]
            li_ch = cv[li_ch0(c):li_ch0(c) + H] if n_hp else np.zeros(H)
            li_dis = cv[li_dis0(c):li_dis0(c) + H] if n_hp else np.zeros(H)
            li_soc = cv[li_soc0(c):li_soc0(c) + H] if n_hp else np.zeros(H)
            hp_direct = np.zeros(H)
            hp_from_batt = np.zeros(H)
            hp_un = np.zeros(H)
            hp_load = np.zeros(H)
            for j in hp_idx:
                p = hp_pos[j]
                _, load, cop = bands[j]
                hp_direct += cv[hp_direct0(p, c):hp_direct0(p, c) + H]
                hp_from_batt += cv[hp_from_batt0(p, c):hp_from_batt0(p, c) + H]
                hp_un += cv[hp_un0(p, c):hp_un0(p, c) + H]
                hp_load += load * shape24
            ihb_ch = np.zeros(H)
            ihb_dis = np.zeros(H)
            ihb_soc = np.zeros(H)
            ihb_un = np.zeros(H)
            ihb_load = np.zeros(H)
            for j in ihb_idx:
                p = ihb_pos[j]
                _, load, _cop = bands[j]
                ihb_ch += cv[ihb_ch0(p, c):ihb_ch0(p, c) + H]
                ihb_dis += cv[ihb_dis0(p, c):ihb_dis0(p, c) + H]
                ihb_soc += cv[ihb_soc0(p, c):ihb_soc0(p, c) + H]
                ihb_un += cv[ihb_un0(p, c):ihb_un0(p, c) + H]
                ihb_load += load * shape24
            for t in range(H):
                rows.append({
                    "rep_day": c,
                    "weight_days": float(weights[c]),
                    "hour": t,
                    "solar_available_MW": float(solar_mw[t]),
                    "solar_to_hp_direct_MW": float(hp_direct[t]),
                    "solar_to_liion_charge_MW": float(li_ch[t]),
                    "solar_to_ihb_charge_MW": float(ihb_ch[t]),
                    "liion_discharge_to_hp_MW": float(li_dis[t]),
                    "liion_soc_MWh": float(li_soc[t]),
                    "hp_electric_in_MW": float(hp_direct[t] + hp_from_batt[t]),
                    "hp_heat_out_MW": float(
                        sum(
                            (cv[hp_direct0(hp_pos[j], c) + t]
                             + cv[hp_from_batt0(hp_pos[j], c) + t])
                            * bands[j][2]
                            for j in hp_idx
                        )
                    ),
                    "hp_load_MW": float(hp_load[t]),
                    "hp_unserved_MW": float(hp_un[t]),
                    "ihb_charge_MW": float(ihb_ch[t]),
                    "ihb_discharge_heat_MW": float(ihb_dis[t]),
                    "ihb_soc_MWh": float(ihb_soc[t]),
                    "ihb_load_MW": float(ihb_load[t]),
                    "ihb_unserved_MW": float(ihb_un[t]),
                })
        hourly_df = pd.DataFrame(rows)

    return results, hourly_df, True


if __name__ == "__main__":
    print(
        "Multi-band HP (Li-ion) + IHB (Energy Innovation) HiGHS optimizer. "
        "Import and call run_multiband_heatpump_optimization(...)."
    )

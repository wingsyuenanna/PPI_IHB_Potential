# optimize_flatblock_multiband_heatpump.py
# Multi-band heat-pump + IHB optimization (HiGHS).
#
# Extends optimize_flatblock_highs_heat_battery.py from a single resistive store to
# B parallel temperature bands sharing ONE on-site solar array. Each band has its own
# converter (heat pump for <200 C via COP>1, resistive for >200 C via COP~1), its own
# thermal store, and its own flat load. The heat-pump effect is the COP multiplier in the
# charge->heat conversion: 1 MWh of solar electricity becomes COP MWh of stored heat, so
# low-temperature bands need far less solar (and land).
#
# Storage uses the flat treatment (no usable-fraction / T_min penalty): soc_b <= E_TES_b.
# All electricity is on-site solar; there is no grid. Currency follows input_costs (USD).

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from highspy import Highs, HighsModelStatus


def _crf(discount_rate: float, lifetime_years: int) -> float:
    r = float(discount_rate)
    n = int(lifetime_years)
    if n <= 0:
        raise ValueError("lifetime_years must be > 0")
    if r <= 0:
        return 1.0 / n
    return r / (1.0 - (1.0 + r) ** (-n))


# Band -> electricity->heat multiplier (COP). Heat pumps >1; resistive ~1.
DEFAULT_COP_BY_BAND = {
    "heat_below100C_tj": 2.7,
    "heat_100C-200C_tj": 1.8,
    "heat_200C-500C_tj": 1.0,
    "heat_500C-1000C_tj": 1.0,
    "heat_above1000C_tj": 1.0,
}
# Band -> converter capital cost ($/MW-thermal), from the manuscript conversion costs
# (heat pumps are dearer per kW than resistive elements).
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
    VoLL: float = 0.0,
    project_start_year: int = 2025,
) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame], bool]:
    """Minimize LCOH for one shared solar array + per-band heat-pump/resistive + storage.

    band_loads maps a temperature-band name to its flat load (MW_th). Only positive-load
    bands are modelled. Returns (results, hourly_df, ok)."""
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
    e_capex = capex_kwh * 1000.0  # $/MWh
    tes_energy_annual_per_mwh = e_capex * (_crf(disc, life) + opex_frac)
    conv_annual_factor = _crf(disc, conv_lifetime_years) + conv_opex_frac  # applied to $/MW

    rte = float(np.clip(round_trip_efficiency, 0.05, 0.999))
    eta = float(np.sqrt(rte))          # symmetric charge/discharge storage efficiency
    inv = float(np.clip(inverter_efficiency, 0.5, 1.0))
    h_max = float(max(0.5, max_storage_hours))
    ratio_cd = float(max(charge_discharge_ratio_min, 1e-6))

    ydf = solar_profile_df[solar_profile_df["year"] == solar_profile_df["year"].iloc[0]].copy()
    g = ydf["P_kWperkWp"].to_numpy(dtype=float)
    hours = len(g)

    bands = [(b, float(load)) for b, load in band_loads.items() if load and load > 0]
    if not bands:
        return None, None, False
    nb = len(bands)
    total_load_MW = sum(load for _, load in bands)
    annual_load_MWh = total_load_MW * hours

    # ── Variable layout ─────────────────────────────────────────────────────
    h = Highs()
    h.silent()
    INF = float("inf")
    solar_ub = max_solar_mw if (max_solar_mw and max_solar_mw > 0) else INF
    # Variables must be added in the same order as their assigned indices so HiGHS
    # column numbers match the `ix` map.
    h.addVar(0, solar_ub)  # 0: S_MW (shared solar)
    ix: Dict[tuple, int] = {}
    col = 1
    for b, _ in bands:
        h.addVar(0, INF); h.addVar(0, INF); h.addVar(0, INF)  # P_ch, P_dis, E
        ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")] = col, col + 1, col + 2
        col += 3
    n_cap = col
    for j, (b, _) in enumerate(bands):
        base = n_cap + j * 5 * hours
        ix[(b, "solar_used")] = base
        ix[(b, "charge")] = base + hours
        ix[(b, "discharge")] = base + 2 * hours
        ix[(b, "soc")] = base + 3 * hours
        ix[(b, "unserved")] = base + 4 * hours
        for _ in range(5 * hours):  # solar_used, charge, discharge, soc, unserved
            h.addVar(0, INF)

    # ── Objective (minimize total annual cost / annual load = LCOH) ──────────
    h.changeColCost(0, solar_cost_per_mw / annual_load_MWh)
    for b, _ in bands:
        cop = cop_by_band.get(b, 1.0)
        # converter rated on thermal charge power = cop * P_charge(elec); annualized.
        conv_annual_per_mw_elec = conv_capex_thermal_by_band.get(b, 200_000.0) * cop * conv_annual_factor
        h.changeColCost(ix[(b, "P_ch")], conv_annual_per_mw_elec / annual_load_MWh)
        h.changeColCost(ix[(b, "E")], tes_energy_annual_per_mwh / annual_load_MWh)
        base = ix[(b, "unserved")]
        for t in range(hours):
            h.changeColCost(base + t, VoLL / annual_load_MWh)

    # ── Constraints ─────────────────────────────────────────────────────────
    def row(lo, hi, cols, coeffs):
        h.addRow(lo, hi, len(cols), np.array(cols, dtype=np.int32), np.array(coeffs, dtype=np.float64))

    for b, load in bands:
        cop = cop_by_band.get(b, 1.0)
        Pch, Pdis, E = ix[(b, "P_ch")], ix[(b, "P_dis")], ix[(b, "E")]
        su, ch, dis, sc, un = (ix[(b, k)] for k in ("solar_used", "charge", "discharge", "soc", "unserved"))
        row(-INF, 0, [E, Pdis], [1.0, -h_max])            # duration: E <= h_max*P_dis
        row(0, INF, [Pch, Pdis], [1.0, -ratio_cd])         # P_ch >= ratio*P_dis
        # Unserved is soft: penalized at VoLL in the objective, not hard-capped, so a
        # land-limited site stays feasible and reports its achievable reliability instead
        # of failing. availability_factor is advisory here.
        for t in range(hours):
            # AC bus: inv*solar_used - inv*charge + inv*discharge + unserved = load
            row(load, load, [su + t, ch + t, dis + t, un + t], [inv, -inv, inv, 1.0])
            # SOC dynamics: soc[t] = soc[t-1] + cop*eta*charge - discharge/eta
            if t == 0:
                row(0, 0, [sc + t, ch + t, dis + t], [1.0, -cop * eta, 1.0 / eta])
            else:
                row(0, 0, [sc + t, sc + t - 1, ch + t, dis + t], [1.0, -1.0, -cop * eta, 1.0 / eta])
            row(-INF, 0, [sc + t, E], [1.0, -1.0])          # SOC ceiling (flat: no usable frac)
            row(-INF, 0, [ch + t, Pch], [1.0, -1.0])         # charge power
            row(-INF, 0, [dis + t, Pdis], [1.0, -1.0])       # discharge power

    # Shared solar coupling per hour: sum_b solar_used_b[t] <= S_MW * g[t]
    for t in range(hours):
        cols = [ix[(b, "solar_used")] + t for b, _ in bands] + [0]
        row(-INF, 0, cols, [1.0] * nb + [-g[t]])

    # ── Solve ───────────────────────────────────────────────────────────────
    t0 = time.time()
    h.minimize()
    elapsed = time.time() - t0
    if h.getModelStatus() != HighsModelStatus.kOptimal:
        print(f"⚠️ site {site_id}: not optimal ({h.getModelStatus()})")
        return None, None, False

    # ── Extract ─────────────────────────────────────────────────────────────
    S_opt = float(h.variableValue(0))
    annual_solar_cost = solar_cost_per_mw * S_opt
    per_band = {}
    total_unserved = 0.0
    annual_conv_cost = annual_tes_cost = 0.0
    solar_used_tot = np.zeros(hours)
    for b, load in bands:
        cop = cop_by_band.get(b, 1.0)
        Pch = float(h.variableValue(ix[(b, "P_ch")]))
        Pdis = float(h.variableValue(ix[(b, "P_dis")]))
        E = float(h.variableValue(ix[(b, "E")]))
        un = np.array([h.variableValue(ix[(b, "unserved")] + t) for t in range(hours)])
        su = np.array([h.variableValue(ix[(b, "solar_used")] + t) for t in range(hours)])
        solar_used_tot += su
        total_unserved += un.sum()
        conv_c = conv_capex_thermal_by_band.get(b, 200_000.0) * cop * conv_annual_factor * Pch
        tes_c = tes_energy_annual_per_mwh * E
        annual_conv_cost += conv_c
        annual_tes_cost += tes_c
        per_band[b] = {
            "load_MW": load, "cop": cop, "P_charge_MW": Pch, "P_discharge_MW": Pdis,
            "E_TES_MWh": E, "unserved_MWh": float(un.sum()),
        }

    annual_unserved_cost = total_unserved * VoLL
    total_cost = annual_solar_cost + annual_conv_cost + annual_tes_cost + annual_unserved_cost
    total_lcoh = total_cost / annual_load_MWh
    energy_served = total_load_MW * hours - total_unserved
    reliability = energy_served / (total_load_MW * hours) * 100
    land_mw = S_opt

    results = {
        "site": site_id,
        "n_bands": nb,
        "total_load_MW": total_load_MW,
        "S_opt_MW": S_opt,
        "solar_per_load_MWdc_per_MWth": S_opt / total_load_MW if total_load_MW else np.nan,
        "conv_capex_annual": annual_conv_cost,
        "storage_energy_MWh_total": sum(v["E_TES_MWh"] for v in per_band.values()),
        "LCOH_total_$perMWh": total_lcoh,
        "LCOH_solar_$perMWh": annual_solar_cost / annual_load_MWh,
        "LCOH_converter_$perMWh": annual_conv_cost / annual_load_MWh,
        "LCOH_storage_$perMWh": annual_tes_cost / annual_load_MWh,
        "LCOH_unserved_$perMWh": annual_unserved_cost / annual_load_MWh,
        "Reliability_%": reliability,
        "Unserved_MWh": total_unserved,
        "hp_load_MW": sum(v["load_MW"] for b, v in per_band.items() if v["cop"] > 1.0),
        "ihb_load_MW": sum(v["load_MW"] for b, v in per_band.items() if v["cop"] <= 1.0),
        "solve_seconds": elapsed,
        "project_start_year": int(project_start_year),
        "bands": per_band,
    }
    hourly_df = pd.DataFrame({
        "Month": ydf["timestamp"].dt.month.values,
        "Day": ydf["timestamp"].dt.day.values,
        "Hour": ydf["timestamp"].dt.hour.values,
        "Solar_available_MW": g * S_opt,
        "Solar_used_MW": solar_used_tot,
        "Curtail_MW": np.maximum(g * S_opt - solar_used_tot, 0),
    })
    return results, hourly_df, True


if __name__ == "__main__":
    print("Multi-band heat-pump + IHB HiGHS optimizer. Import and call "
          "run_multiband_heatpump_optimization(...).")

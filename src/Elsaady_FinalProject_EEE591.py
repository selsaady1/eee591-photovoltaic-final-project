"""
Residential Grid-Connected PV + Battery System:
Net Metering vs. Net Billing Techno-Economic Analysis
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================================
# CONFIGURATION 
# ============================================================================

# System specifications (from Final Project EEE 465_591.docx)
system_W = 5000  # 5 kW residential system
capacity = 14  # kWh battery capacity (Tesla Powerwall class)

# Component efficiencies (from Section 4-2 reference)
PLACEHOLDER_eta_inv = 0.95  # Inverter efficiency (~95%)
PLACEHOLDER_eta_wire = 0.97  # Wiring losses (≤3%)
PLACEHOLDER_eta_battery_ch = 0.95  # Battery charge efficiency
PLACEHOLDER_eta_battery_dis = 0.95  # Battery discharge efficiency

# Battery SOC constraints
SOC_min = 0.1  # Minimum 10% SOC
SOC_max = 1.0  # Maximum 100% SOC

# Financial parameters (from financial functions example and project docs)
dollars_per_watt = PLACEHOLDER_dollars_per_watt = 2.0  # $/W (from example)
battery_per_kWh = 300  # $/kWh (from project brief)
n = 25  # System lifetime in years
battery_replace_time = 7  # years
interest_rate = 0.03      # 3% discount rate
O_and_M_percentage = 0.005  # 0.5% of initial cost (from example)
O_and_M_growth = PLACEHOLDER_O_and_M_growth = 0.035  # 3.5% growth (from example)

# Electricity rates
monthly_fee = 32.44  # SRP Monthly Fee

# Three-season TOU structure
season_1 = [1, 2, 3, 4, 11, 12]  # Winter
season_2 = [5, 6, 9, 10]  # Shoulder (Spring/Fall)
season_3 = [7, 8]  # Summer

# Peak time definitions
peak_time_1 = [5, 6, 7, 8, 17, 18, 19, 20]  # Winter on-peak hours
peak_time_2 = [14, 15, 16, 17, 18, 19]  # Shoulder on-peak hours
peak_time_3 = [14, 15, 16, 17, 18, 19]  # Summer on-peak hours

# Rates in cents/kWh
rates_1 = [6.91, 9.51]  # Winter [off-peak, on-peak]
rates_2 = [7.27, 20.94]  # Shoulder [off-peak, on-peak]
rates_3 = [7.3, 24.09]  # Summer [off-peak, on-peak]

# Buy-back rate for Net Billing
# Note: using separate variables for clarity: is_net_metering (bool), buyback_rate (float)
net_billing_buyback_rate = 2.81  # cents/kWh (SRP rate)
# Alternative from project brief mentions $0.06/kWh = 6 cents/kWh
# Using SRP value: 2.81 cents/kWh

# ---- File locations ----
LOAD_CSV = "load_data.csv"   # instructor sample load file (8760 rows)
PV_CSV = "pv_profile.csv"   # the instructor-provided hourly PV file
PV_COL = "kWh"              # column name containing hourly PV production (kWh)
REQUIRE_8760 = True         # enforce exactly 8760 rows

# ============================================================================
# FINANCIAL FUNCTIONS
# ============================================================================

def NPV_from_FV(FV, rate, time_period):
    """Return the NPV given future value (FV), the interest rate (rate), 
    with the future value at a time = time_period in the future
    
    From: Code snip for financial functions.py
    """
    factor = pow((1+rate), -1*time_period)
    NPV = factor * FV
    return NPV, factor

def A_from_NPV(NPV, rate, time_period):
    """Return the annualized value given Net Present Value (NPV), the interest rate (rate), 
    and the period over which the NPV is annualized
    
    From: Code snip for financial functions.py
    """
    factor = rate*pow((1+rate), time_period)/(pow((1+rate), time_period)-1)
    A = factor * NPV
    return A, factor

def NPV_from_geo(geo, interest_rate, growth_rate, n):
    """Return the NPV given geometrically increasing initial value of geo.
    
    From: Code snip for financial functions.py
    """
    if interest_rate == growth_rate:
        factor = n/(1 + interest_rate)        
    else:
        factor = (1/(interest_rate - growth_rate))* (1 - pow((1+ interest_rate), -1*n)*pow((1+ growth_rate), n))
    NPV = factor * geo
    return NPV, factor

# ============================================================================
# TIME ARRAYS
# ============================================================================

def build_time_arrays():
    """Generate hour, day_number, hour_day, and month arrays
    
    From: Code snip for arrays for day number hour of the day and month.py
    """
    hour = np.arange(0.0, 8760.0, 1)  # hours 0..8759
    day_number, hour_day = divmod(hour, 24)
    
    # Month end hour indices (0-based, exclusive): 744, 1416, ...
    month_ends = np.array([744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016, 8760])
    month = np.zeros(8760, dtype=int)
    start = 0
    for m, end in enumerate(month_ends, start=1):
        month[start:end] = m
        start = end
    
    # Weekend array
    weekend_days = [0.0, 0, 0, 0, 0, 1.0, 1.0]
    weekend = np.tile(np.repeat(weekend_days, 24), 52)
    weekend = np.append(weekend, np.repeat(0, 24))  # extra day to reach 8760
    
    return hour, day_number.astype(int), hour_day.astype(int) + 1, month, weekend

# ============================================================================
# ELECTRICITY RATE ARRAY
# ============================================================================

def build_rate_array(month, hour_day, weekend):
    """Build hourly electricity rate array based on TOU structure"""
    rate = np.zeros(len(month))
    
    for idx, m in enumerate(month):
        if m in season_1:
            rate[idx] = rates_1[1] if (hour_day[idx] in peak_time_1) else rates_1[0]
        elif m in season_2:
            if (hour_day[idx] in peak_time_2) and (weekend[idx] == 0):
                rate[idx] = rates_2[1]
            else:
                rate[idx] = rates_2[0]
        elif m in season_3:
            if (hour_day[idx] in peak_time_3) and (weekend[idx] == 0):
                rate[idx] = rates_3[1]
            else:
                rate[idx] = rates_3[0]
    
    # Safety net: if any hour stayed 0.0, set it to its season's off-peak
    zero_idx = np.where(rate == 0.0)[0]
    if len(zero_idx) > 0:
        for idx in zero_idx:
            if month[idx] in season_1: rate[idx] = rates_1[0]
            elif month[idx] in season_2: rate[idx] = rates_2[0]
            elif month[idx] in season_3: rate[idx] = rates_3[0]
    
    return rate

# ============================================================================
# PV GENERATION MODEL
# ============================================================================

def generate_pv_profile(hour_day, month, path_candidates=None, col_candidates=None):
    """
    STRICT: Load hourly PV production (kWh) from the INSTRUCTOR file only.
    Expects pv_profile.csv with a 'kWh' column and exactly 8760 rows.
    Returns np.zeros(8760) and prints an abort message if the file is invalid/missing.
    """
    import os

    # Only accept the explicitly allowed instructor file/column
    p = PV_CSV
    c = PV_COL

    if not os.path.exists(p):
        print(f"  MISSING PV FILE: '{p}' not found in the working directory.")
        print("  Provide the instructor PV CSV before running the analysis.")
        return np.zeros(8760)

    try:
        df = pd.read_csv(p)
    except Exception as e:
        print(f"  ERROR: Could not read '{p}': {e}")
        return np.zeros(8760)

    if c not in df.columns:
        print(f"  ERROR: Required column '{c}' not found in '{p}'. Columns are: {list(df.columns)}")
        return np.zeros(8760)

    pv = np.asarray(df[c].values, dtype=float)
    if REQUIRE_8760 and len(pv) != 8760:
        print(f"  ERROR: '{p}' must have exactly 8760 rows in column '{c}' (found {len(pv)}).")
        return np.zeros(8760)

    # Clean any NaNs or tiny negatives
    pv = np.nan_to_num(pv, nan=0.0)
    pv[pv < 0] = 0.0

    print(f"  Loaded PV profile from '{p}' using column '{c}'")
    print(f"  Annual PV generation: {pv.sum():.2f} kWh")
    return pv

# ============================================================================
# BATTERY DISPATCH
# ============================================================================

def battery_dispatch(Load, PV_output, capacity, eta_ch, eta_dis):
    """Simulate battery charge/discharge and compute grid exchanges
    
    Returns:
        PV_unused: Energy sent to grid (kWh per hour)
        load_unmet: Energy drawn from grid (kWh per hour)
        SOC_history: Battery state of charge history
    """
    PV_unused = np.zeros(8760)
    load_unmet = np.zeros(8760)
    SOC = np.zeros(8761)  # One extra for initial condition
    SOC[0] = 0.5  # Start at 50% SOC
    
    for h in range(8760):
        net_energy = PV_output[h] - Load[h]  # Positive = excess PV
        
        if net_energy > 0:  # Excess PV: charge battery or export
            # Try to charge battery
            available_capacity = (SOC_max - SOC[h]) * capacity
            charge_energy = min(net_energy * eta_ch, available_capacity)
            SOC[h+1] = SOC[h] + charge_energy / capacity
            
            # Remaining goes to grid
            PV_unused[h] = net_energy - charge_energy / eta_ch
            load_unmet[h] = 0
        
        else:  # Deficit: discharge battery or import
            deficit = -net_energy
            # Try to discharge battery
            available_discharge = (SOC[h] - SOC_min) * capacity * eta_dis
            discharge_energy = min(deficit, available_discharge)
            SOC[h+1] = SOC[h] - discharge_energy / (capacity * eta_dis)
            
            # Remaining comes from grid
            load_unmet[h] = deficit - discharge_energy
            PV_unused[h] = 0
    
    return PV_unused, load_unmet, SOC[:-1]

# ============================================================================
# BILLING CALCULATION
# ============================================================================

def calculate_annual_bill(load_unmet, PV_unused, rate, is_net_metering, buyback_rate_cents):
    """Calculate annual electricity bill
    
    Args:
        load_unmet: Hourly grid import (kWh)
        PV_unused: Hourly grid export (kWh)
        rate: Hourly import rate (cents/kWh)
        is_net_metering: If True, export credited at import rate
        buyback_rate_cents: Export rate for net billing (cents/kWh)
    """
    # Monthly service charge
    cost_monthly_fee = monthly_fee * 12
    
    # Electricity usage charges
    if is_net_metering:
        # Net metering: export credited at same rate as import
        buy_back = rate
    else:
        # Net billing: fixed lower buy-back rate
        buy_back = np.full(8760, buyback_rate_cents)
    
    # Hourly cost calculation
    cost_electricity_usage_hourly = 1e-2 * (rate * load_unmet - buy_back * PV_unused)
    cost_electricity_usage = sum(cost_electricity_usage_hourly)
    
    total_cost = cost_monthly_fee + cost_electricity_usage
    
    return {
        'monthly_fee': cost_monthly_fee,
        'usage_cost': cost_electricity_usage,
        'total_annual_bill': total_cost,
        'hourly_cost': cost_electricity_usage_hourly
    }

# ============================================================================
# FINANCIAL ANALYSIS
# ============================================================================

def calculate_system_economics(annual_bill_solar, annual_bill_baseline, Load):
    """Calculate NPV, annualized cost, LCOE, and payback"""
    # Initial costs
    PV_Initial_cost = dollars_per_watt * system_W
    Initial_battery_cost = battery_per_kWh * capacity  # $
    
    # Battery replacement NPV
    npv_battery_cost = Initial_battery_cost  
    count = 1
    while count * battery_replace_time <= n:
        battery_NPV, factor = NPV_from_FV(Initial_battery_cost, interest_rate, 
                                          battery_replace_time * count)
        npv_battery_cost = npv_battery_cost + battery_NPV
        count = count + 1
    
    # O&M costs
    Initial_OM_cost = O_and_M_percentage * PV_Initial_cost
    NPV_OM, factor = NPV_from_geo(Initial_OM_cost, interest_rate, O_and_M_growth, n)
    
    # Total NPV
    NPV_system = PV_Initial_cost + npv_battery_cost + NPV_OM
    
    # Annualized costs
    A_battery_cost, factor = A_from_NPV(npv_battery_cost, interest_rate, n)
    A_PV, factor = A_from_NPV(PV_Initial_cost, interest_rate, n)
    A_OM, factor = A_from_NPV(NPV_OM, interest_rate, n)
    A_system = A_battery_cost + A_PV + A_OM
    
    # Annual savings
    annual_savings = annual_bill_baseline - annual_bill_solar
    
    # LCOE reported here as "grid-equivalent" (annualized cost per kWh of annual load),
    # normalized by sum(Load).
    total_energy = sum(Load)
    LCOE = A_system / total_energy
    
    # Simple payback
    initial_investment = PV_Initial_cost + Initial_battery_cost
    if annual_savings > 0:
        payback_years = initial_investment / annual_savings
    else:
        payback_years = np.inf
    
    # NPV of savings stream
    NPV_savings = 0
    for year in range(1, n+1):
        savings_npv, _ = NPV_from_FV(annual_savings, interest_rate, year)
        NPV_savings += savings_npv
    
    net_npv = NPV_savings - NPV_system
    
    return {
        'initial_investment': initial_investment,
        'PV_cost': PV_Initial_cost,
        'battery_cost': Initial_battery_cost,
        'NPV_system': NPV_system,
        'NPV_savings': NPV_savings,
        'net_NPV': net_npv,
        'annualized_cost': A_system,
        'annual_savings': annual_savings,
        'LCOE': LCOE,
        'payback_years': payback_years
    }

# ============================================================================
# SENSITIVITY ANALYSIS (no invented ranges)
# ============================================================================

def run_economics_with_params(Load, rate, PV_output, battery_cost_per_kWh, discount_rate):
    """Recompute full bills and economics for given parameters.
    Caller supplies the values (no default assumptions).
    """
    global battery_per_kWh, interest_rate

    # Save originals
    _orig_bpk = battery_per_kWh
    _orig_ir  = interest_rate

    # Apply test values
    battery_per_kWh = battery_cost_per_kWh
    interest_rate   = discount_rate

    # Baseline (no solar)
    baseline_import = Load
    baseline_export = np.zeros(8760)
    baseline_bill = calculate_annual_bill(baseline_import, baseline_export, rate,
                                          False, net_billing_buyback_rate)

    # Dispatch with current PV_output
    PV_unused, load_unmet, _ = battery_dispatch(Load, PV_output, capacity,
                                                PLACEHOLDER_eta_battery_ch,
                                                PLACEHOLDER_eta_battery_dis)

    # Policies
    nm_bill = calculate_annual_bill(load_unmet, PV_unused, rate, True, 0)
    nb_bill = calculate_annual_bill(load_unmet, PV_unused, rate, False, net_billing_buyback_rate)

    nm_econ = calculate_system_economics(nm_bill['total_annual_bill'], baseline_bill['total_annual_bill'], Load)
    nb_econ = calculate_system_economics(nb_bill['total_annual_bill'], baseline_bill['total_annual_bill'], Load)

    # Restore originals
    battery_per_kWh = _orig_bpk
    interest_rate   = _orig_ir

    return {
        'baseline_bill': baseline_bill,
        'net_metering': {'bill': nm_bill, 'economics': nm_econ},
        'net_billing':  {'bill': nb_bill, 'economics': nb_econ},
    }


def sensitivity_economics(Load, rate, PV_output, battery_cost_list, discount_rate_list):
    """Sensitivity analysis with explicit parameter ranges.
    Caller must pass explicit lists.
    Returns a DataFrame of key metrics for each (battery_cost, discount_rate) pair.
    """
    rows = []
    for b_cost in battery_cost_list:
        for dr in discount_rate_list:
            res = run_economics_with_params(Load, rate, PV_output, b_cost, dr)
            nm = res['net_metering']['economics']
            nb = res['net_billing']['economics']
            rows.append({
                'battery_$/kWh': b_cost,
                'discount_rate': dr,
                'nm_annual_savings': nm['annual_savings'],
                'nm_payback_years': nm['payback_years'],
                'nm_net_NPV': nm['net_NPV'],
                'nb_annual_savings': nb['annual_savings'],
                'nb_payback_years': nb['payback_years'],
                'nb_net_NPV': nb['net_NPV'],
            })
    return pd.DataFrame(rows)

def plot_sensitivity_table(df, fname='plot5_sensitivity.png'):
    """Bar chart of net NPV vs battery $/kWh for each policy (single discount rate).
    Uses only the sensitivity table produced by sensitivity_economics().
    """
    try:
        # Expect one discount_rate; if multiple were passed, pick the first for plotting
        dr = df['discount_rate'].unique()[0]
        sub = df[df['discount_rate'] == dr].copy()
        x = np.arange(len(sub))
        width = 0.35

        fig = plt.figure(figsize=(10, 6))
        plt.bar(x - width/2, sub['nm_net_NPV'], width, label='Net Metering')
        plt.bar(x + width/2, sub['nb_net_NPV'], width, label='Net Billing')
        plt.xticks(x, [f"{int(b)}" for b in sub['battery_$/kWh']])
        plt.xlabel('Battery cost ($/kWh)')
        plt.ylabel('Net NPV (25 yr, $)')
        plt.title(f'Sensitivity: Net NPV vs Battery $/kWh (discount rate={dr:.2%})')
        plt.grid(True, axis='y', alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"Sensitivity plot saved to: {fname}")
        plt.close(fig)
    except Exception as e:
        print(f"Sensitivity plotting skipped due to: {e}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("="*70)
    print("PV + Battery System: Net Metering vs. Net Billing Analysis")
    print("="*70)
    print()
    
    # 1. Load data
    print("Loading hourly load data...")
    load_df = pd.read_csv(LOAD_CSV)
    # if the first row is blank, this safely removes it without inventing data
    if 'kWh' not in load_df.columns:
        raise ValueError(f"'kWh' column not found in {LOAD_CSV}. Columns: {list(load_df.columns)}")
    load_df = load_df.dropna(subset=['kWh']).reset_index(drop=True)
    Load = load_df['kWh'].astype(float).values
    print(f"  Loaded {len(Load)} hourly load values")
    print(f"  Annual energy consumption: {Load.sum():.2f} kWh")
    print()
    
    # 2. Build time arrays
    print("Building time arrays...")
    hour, day_number, hour_day, month, weekend = build_time_arrays()
    print("  Generated hour, day, month, and weekend arrays")
    print()
    
    # 3. Build rate array
    print("Building TOU electricity rate array...")
    rate = build_rate_array(month, hour_day, weekend)
    nz = rate[rate > 0]
    print(f"  Rate range: {nz.min():.2f} - {nz.max():.2f} cents/kWh")
    print()
    
    # 4. Generate PV profile
    print("Generating PV output profile...")
    PV_output = generate_pv_profile(hour_day, month)
    print(f"  Annual PV generation: {PV_output.sum():.2f} kWh")
    print(f"  PV capacity factor: {PV_output.sum()/(system_W*8760/1000)*100:.1f}%")
    print()
    
    # Hard-guard: Prevent "fake" results if PV=0
    if PV_output.sum() <= 0:
        print("\n" + "="*70)
        print("ABORT: PV profile is zero. Provide 'pv_profile.csv' (8760 rows, column 'kWh').")
        print("       Place it in the same folder as this .py file.")
        print("="*70)
        print("\nCalculating baseline bill only for context...")
        baseline_import = Load
        baseline_export = np.zeros(8760)
        baseline_bill = calculate_annual_bill(baseline_import, baseline_export, rate, 
                                             False, net_billing_buyback_rate)
        print(f"Baseline annual bill: ${baseline_bill['total_annual_bill']:.2f}")
        return {
            'baseline_only': True,
            'baseline_bill': baseline_bill,
            'Load': Load  # include for completeness, even in baseline mode
        }
    
    # 5. Calculate baseline bill (no solar)
    print("Calculating baseline bill (no solar)...")
    baseline_import = Load
    baseline_export = np.zeros(8760)
    baseline_bill = calculate_annual_bill(baseline_import, baseline_export, rate, 
                                         False, net_billing_buyback_rate)
    print(f"  Baseline annual bill: ${baseline_bill['total_annual_bill']:.2f}")
    print()
    
    # 6. Simulate battery dispatch
    print("Simulating battery dispatch...")
    PV_unused, load_unmet, SOC = battery_dispatch(Load, PV_output, capacity,
                                                   PLACEHOLDER_eta_battery_ch,
                                                   PLACEHOLDER_eta_battery_dis)
    print(f"  Annual grid import: {load_unmet.sum():.2f} kWh")
    print(f"  Annual grid export: {PV_unused.sum():.2f} kWh")
    print(f"  Battery cycled energy: {(Load.sum() - load_unmet.sum() - PV_output.sum() + PV_unused.sum()):.2f} kWh")
    print()
    
    # 7. Calculate bills for both policies
    print("="*70)
    print("POLICY COMPARISON")
    print("="*70)
    
    # Net Metering
    print("\n[1] NET METERING (export = import rate)")
    nm_bill = calculate_annual_bill(load_unmet, PV_unused, rate, True, 0)
    print(f"  Annual bill: ${nm_bill['total_annual_bill']:.2f}")
    print(f"    - Monthly fees: ${nm_bill['monthly_fee']:.2f}")
    print(f"    - Usage charges: ${nm_bill['usage_cost']:.2f}")
    
    nm_econ = calculate_system_economics(nm_bill['total_annual_bill'],
                                         baseline_bill['total_annual_bill'],
                                         Load)
    print(f"  Annual savings: ${nm_econ['annual_savings']:.2f}")
    print(f"  Initial investment: ${nm_econ['initial_investment']:.2f}")
    print(f"  NPV (25 years): ${nm_econ['net_NPV']:.2f}")
    print(f"  LCOE: ${nm_econ['LCOE']:.4f}/kWh")
    print(f"  Simple payback: {nm_econ['payback_years']:.1f} years")
    
    # Net Billing
    print("\n[2] NET BILLING (export = {} cents/kWh)".format(net_billing_buyback_rate))
    nb_bill = calculate_annual_bill(load_unmet, PV_unused, rate, False, 
                                    net_billing_buyback_rate)
    print(f"  Annual bill: ${nb_bill['total_annual_bill']:.2f}")
    print(f"    - Monthly fees: ${nb_bill['monthly_fee']:.2f}")
    print(f"    - Usage charges: ${nb_bill['usage_cost']:.2f}")
    
    nb_econ = calculate_system_economics(nb_bill['total_annual_bill'],
                                         baseline_bill['total_annual_bill'],
                                         Load)
    print(f"  Annual savings: ${nb_econ['annual_savings']:.2f}")
    print(f"  Initial investment: ${nb_econ['initial_investment']:.2f}")
    print(f"  NPV (25 years): ${nb_econ['net_NPV']:.2f}")
    print(f"  LCOE: ${nb_econ['LCOE']:.4f}/kWh")
    print(f"  Simple payback: {nb_econ['payback_years']:.1f} years")
    
    # --- Sanity check: policies should differ when PV>0 ---
    bill_diff = abs(nm_bill['total_annual_bill'] - nb_bill['total_annual_bill'])
    if bill_diff < 0.50:  # within 50 cents = essentially the same
        print("\nWARNING: Net Metering and Net Billing annual bills are nearly identical.")
        print("         Check PV profile magnitude/timing and buyback settings.")
    else:
        print(f"\nPolicy sanity check passed: NM vs NB differ by ${bill_diff:.2f} annually.")
    
    # Comparison
    print("\n" + "="*70)
    print("SUMMARY COMPARISON")
    print("="*70)
    print(f"{'Metric':<30} {'Net Metering':>15} {'Net Billing':>15}")
    print("-"*70)
    print(f"{'Annual Bill':<30} ${nm_bill['total_annual_bill']:>14.2f} ${nb_bill['total_annual_bill']:>14.2f}")
    print(f"{'Annual Savings':<30} ${nm_econ['annual_savings']:>14.2f} ${nb_econ['annual_savings']:>14.2f}")
    print(f"{'Net NPV (25 yr)':<30} ${nm_econ['net_NPV']:>14.2f} ${nb_econ['net_NPV']:>14.2f}")
    print(f"{'LCOE ($/kWh)':<30} ${nm_econ['LCOE']:>14.4f} ${nb_econ['LCOE']:>14.4f}")
    print(f"{'Payback (years)':<30} {nm_econ['payback_years']:>15.1f} {nb_econ['payback_years']:>15.1f}")
    print("="*70)
    
    # 9. SENSITIVITY ANALYSIS (executed per rubric: vary inputs and observe outputs)
    print("\n" + "="*70)
    print("SENSITIVITY ANALYSIS (Battery cost only; discount rate fixed)")
    print("="*70)

    # Vary one input (battery cost) around the baseline.
    # Using ±25% around the provided $300/kWh baseline.
    battery_cost_list   = [0.75 * battery_per_kWh, battery_per_kWh, 1.25 * battery_per_kWh]
    discount_rate_list  = [interest_rate]  # keep 3%

    sens_df = sensitivity_economics(Load, rate, PV_output, battery_cost_list, discount_rate_list)

    # Pretty-print the table
    with pd.option_context('display.max_columns', None, 'display.width', 120):
        print(sens_df.to_string(index=False))

    # Save for report/slide appendix
    sens_csv = 'sensitivity_results.csv'
    sens_df.to_csv(sens_csv, index=False)
    print(f"\nSaved sensitivity table to: {sens_csv}")

    # Optional figure for slides (no new data—just visualize the computed table)
    plot_sensitivity_table(sens_df, fname='plot5_sensitivity.png')
    
    # 8. Return structured results
    return {
        'net_metering': {
            'bill': nm_bill,
            'economics': nm_econ
        },
        'net_billing': {
            'bill': nb_bill,
            'economics': nb_econ
        },
        'baseline_bill': baseline_bill,
        'Load': Load,
        'PV_output': PV_output,
        'PV_unused': PV_unused,
        'load_unmet': load_unmet,
        'SOC': SOC,
        'rate': rate,
        'month': month
    }

# ============================================================================
# PLOTTING (optional, only if data exists)
# ============================================================================

def plot_load_profile(Load, month, fname='plot0_load_profile.png'):
    """
    Generate a bar chart of total monthly energy consumption.
    """
    try:
        monthly_load = []
        for m in range(1, 13):
            monthly_load.append(Load[month == m].sum())
        
        months_str = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        fig = plt.figure(figsize=(10, 6))
        plt.bar(months_str, monthly_load)
        plt.xlabel('Month')
        plt.ylabel('Total Energy Consumption (kWh)')
        plt.title('Annual Residential Load Profile by Month')
        plt.grid(True, axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"\nLoad profile plot saved to: {fname}")
        plt.close(fig)
    except Exception as e:
        print(f"Load profile plotting skipped due to: {e}")

def plot_results(results, month):
    """Generate visualization plots - each as separate figure"""
    if any(k not in results for k in ['Load', 'PV_output', 'load_unmet', 'SOC']):
        print("Plots skipped: missing keys in results.")
        return
    
    N = len(results['Load'])
    
    # --- Find Summer Indices (e.g., 3rd week of July) ---
    try:
        summer_start_idx = np.where(month == 7)[0][0] + 24*14 # 3rd week
        if summer_start_idx + 168 > N: # safety check
            summer_start_idx = np.where(month == 7)[0][0]
        summer_day_idx = summer_start_idx + 24 # pick a day
        summer_week_idx = summer_start_idx
    except: # fallback
        summer_day_idx = min(180 * 24, max(0, N - 24))
        summer_week_idx = min(180 * 24, max(0, N - 168))

    # --- Find Winter Indices (e.g., 3rd week of Jan) ---
    try:
        winter_start_idx = np.where(month == 1)[0][0] + 24*14 # 3rd week
        if winter_start_idx + 168 > N: # safety check
            winter_start_idx = np.where(month == 1)[0][0]
        winter_week_idx = winter_start_idx
    except: # fallback
        winter_week_idx = min(30 * 24, max(0, N - 168))

    
    # Plot 1: Typical day energy flow (summer weekday)
    fig1 = plt.figure(figsize=(10, 6))
    hours = np.arange(24)
    plt.plot(hours, results['Load'][summer_day_idx:summer_day_idx+24], 'o-', label='Load')
    plt.plot(hours, results['PV_output'][summer_day_idx:summer_day_idx+24], 's-', label='PV Output')
    plt.plot(hours, results['load_unmet'][summer_day_idx:summer_day_idx+24], '^-', label='Grid Import')
    plt.xlabel('Hour of Day')
    plt.ylabel('Energy (kWh)')
    plt.title('Typical Summer Day Energy Flow (July)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plot1_energy_flow_summer.png', dpi=150, bbox_inches='tight')
    print("\nPlot 1 (Summer Day) saved to: plot1_energy_flow_summer.png")
    plt.close(fig1)
    
    # Plot 2: Battery SOC over a SUMMER week
    fig2 = plt.figure(figsize=(10, 6))
    plt.plot(np.arange(168), results['SOC'][summer_week_idx:summer_week_idx+168])
    plt.axhline(y=SOC_min, color='r', linestyle='--', alpha=0.5, label='Min SOC')
    plt.axhline(y=SOC_max, color='r', linestyle='--', alpha=0.5, label='Max SOC')
    plt.xlabel('Hour of Week')
    plt.ylabel('State of Charge')
    plt.title('Battery SOC - Sample Summer Week (July)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plot2_battery_soc_summer.png', dpi=150, bbox_inches='tight')
    print("Plot 2 (Summer SOC) saved to: plot2_battery_soc_summer.png")
    plt.close(fig2)

    # Plot 2b: Battery SOC over a WINTER week
    fig2b = plt.figure(figsize=(10, 6))
    plt.plot(np.arange(168), results['SOC'][winter_week_idx:winter_week_idx+168])
    plt.axhline(y=SOC_min, color='r', linestyle='--', alpha=0.5, label='Min SOC')
    plt.axhline(y=SOC_max, color='r', linestyle='--', alpha=0.5, label='Max SOC')
    plt.xlabel('Hour of Week')
    plt.ylabel('State of Charge')
    plt.title('Battery SOC - Sample Winter Week (January)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plot2b_battery_soc_winter.png', dpi=150, bbox_inches='tight')
    print("Plot 2b (Winter SOC) saved to: plot2b_battery_soc_winter.png")
    plt.close(fig2b)
    
    # Plot 3: Annual cost comparison
    fig3 = plt.figure(figsize=(10, 6))
    policies = ['Baseline\n(No Solar)', 'Net\nMetering', 'Net\nBilling']
    bills = [
        results['baseline_bill']['total_annual_bill'],
        results['net_metering']['bill']['total_annual_bill'],
        results['net_billing']['bill']['total_annual_bill']
    ]
    colors = ['gray', 'green', 'orange']
    bars = plt.bar(policies, bills, color=colors, alpha=0.7)
    plt.ylabel('Annual Bill ($)')
    plt.title('Annual Electricity Bill Comparison')
    plt.grid(True, alpha=0.3, axis='y')
    for bar, bill in zip(bars, bills):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'${bill:.0f}', ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig('plot3_annual_bills.png', dpi=150, bbox_inches='tight')
    print("Plot 3 saved to: plot3_annual_bills.png")
    plt.close(fig3)
    
    # Plot 4: Economic metrics comparison
    fig4 = plt.figure(figsize=(10, 6))
    metrics = ['Annual\nSavings', 'Payback\n(years)']
    nm_vals = [
        results['net_metering']['economics']['annual_savings'],
        results['net_metering']['economics']['payback_years']
    ]
    nb_vals = [
        results['net_billing']['economics']['annual_savings'],
        results['net_billing']['economics']['payback_years']
    ]
    
    x = np.arange(len(metrics))
    width = 0.35
    plt.bar(x - width/2, nm_vals, width, label='Net Metering', color='green', alpha=0.7)
    plt.bar(x + width/2, nb_vals, width, label='Net Billing', color='orange', alpha=0.7)
    plt.xticks(x, metrics)
    plt.legend()
    plt.title('Economic Performance Comparison')
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig('plot4_economics.png', dpi=150, bbox_inches='tight')
    print("Plot 4 saved to: plot4_economics.png")
    plt.close(fig4)
    
    print("\nAll plots saved successfully!")

# ============================================================================
# RUN ANALYSIS
# ============================================================================

if __name__ == "__main__":
    results = main()

    print("\n" + "="*70)
    print("Generating plots...")
    print("="*70)

    try:
        if isinstance(results, dict) and not results.get('baseline_only', False):
            # Call the new load profile plot
            plot_load_profile(results['Load'], results['month'])
            
            # Pass month to the main results plotting function
            plot_results(results, results['month'])
        else:
            print("Plots skipped: baseline-only run (PV profile missing).")
    except Exception as e:
        print(f"Plotting skipped due to: {e}")

    print("\nAnalysis complete!")
    print("\nNote: All PLACEHOLDER_* constants are marked where specific values were not provided.")

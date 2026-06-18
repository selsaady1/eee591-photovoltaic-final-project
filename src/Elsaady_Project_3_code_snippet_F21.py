''' Mini Project 3 Fall 2021
'''
import matplotlib.pyplot as plt
import numpy as np
import photovoltaic as pv
# import photovoltaic_eee465_591_F17 as pv
import time

from numpy import radians as rad

# Enter the J0 and Jsc and n values from Project 2 here

J0 = 2.27207184075e-13 # A/cm²
JL = 0.0379639368734  # A/cm²
Area = 243.36 # cm²
Rseries = 0.6935010143333081 #ohm.cm
voc=pv.cell.Voc(JL,J0)
ff_0=0.804

# --- Part 1a/1b: AM1.5G cell and 72-cell module ---
I_cell_AM15 = JL * Area                  # A    (Jsc [A/cm^2] × area [cm^2])
P_cell_AM15 = voc * JL * ff_0 * Area     # W    (V × A/cm^2 × FF × cm^2)
N_series = 72
P_module_AM15 = N_series * P_cell_AM15   # W    ideal series module

print(f"AM1.5G one-cell current (15.6 cm × 15.6 cm): {I_cell_AM15:.4f} A")
print(f"AM1.5G one-cell MPP power: {P_cell_AM15:.2f} W")
print(f"AM1.5G ideal 72-cell series module MPP power: {P_module_AM15:.1f} W")

# Project #3

# Define Module tilt and module azimuth, alhtough not needed in Project 3

module_azimuth = 180  # point the module south
module_tilt = 0


# Read TMY data file, import by station name

fname = '722780TYA.CSV'
city = fname
station, GMT_offset, latitude, longitude, altitude = np.genfromtxt(fname, max_rows=1, delimiter=",",
                                                                   usecols=(0, 3, 4, 5, 6))
ETR, GHI, DNI, DHI, ambient_temperature  = np.genfromtxt(fname, skip_header=2, delimiter=",", usecols=(2, 4, 7, 10, 31), unpack=True)

module_elevation = latitude

print('station number: ', station)
print('City: ', city)
print('GMT: ', GMT_offset)
print('Latitude (degrees):', latitude)
print('Longitude (degrees):', longitude)
print('Altitude (m): ', altitude)

# details for the plots which makes string to label the plots
details4plot = ' lat: {:.1f}°, long: {:.1f}°, Module el: {}°, az: {}°'.format(
    latitude, longitude, module_elevation, module_azimuth)
print(details4plot)


# ************************************************************
# Project  3 Part 1

# Calculate the light intensity;
# Since JL from project 2 has been calculated at AM1.5G (1000W/m²), 
# we need to divide by 100 and multiply by the DHI and DNI to find JL for every hour of the year
JL_module = (DNI+DHI)*0.001*JL

# This prints the current in mA/cm² from the module for every hour of the year
if 1:  # 1 - plot the data, 0 - turn plot off
    JL_total_mAcm2_h = 1e3 * np.sum(JL_module)  # mA·h/cm^2 over the year (sum of hourly J in A/cm^2 × h)
    plt.title('Current Density from the Module\nTotal JL over year = {:.1f} mA·h/cm²   (AM1.5G Jsc = {:.2f} mA/cm²)'.format(JL_total_mAcm2_h, 1e3*JL))
    plt.plot(1e3*JL_module)
    plt.xlabel('hour of the year')
    plt.ylabel('Current Density in hour interval (mA/cm²)')
    plt.show()

# --- Part 1.c: constant Voc/FF sanity check (per assignment) ---
P_module_const = voc * JL_module * ff_0 * 10.0   # kW/m^2 for each hour

if 1:
    plt.title('Power from the Module (Constant Voc, FF)\n'
              f'Total Energy = {np.sum(P_module_const):.2f} kWh/m²')
    plt.plot(P_module_const)
    plt.xlabel('hour of the year')
    plt.ylabel('Power in hour interval (kW/m²)')
    plt.show()

print('\ncapacity factor = ', 100*np.sum(P_module_const)/(10*8760*JL*voc*ff_0), '%')
print('\n')
print('SUMMARY for Project 3 Part 1.c constant Voc, FF and efficiency ')
print('Energy from Sun over year {:.2f} kWh/m²'.format(np.sum(DNI+DHI)/1000))
print('Energy from Module {:.2f} kWh/m²'.format(np.sum(P_module_const)))
print('Average Efficiency {:.2f}% '.format(100*np.sum(P_module_const)/(np.sum(DNI+DHI)/1000)))


P_module = np.zeros(len(JL_module))  # Re-initialize array for Part 1.d IV curve calculations
efficiency = np.zeros(len(JL_module))  # Set up an array with zeros for the module efficiency in each hour of the year

# Calculate the FF and efficiency for every hour the year
# We can used closed form equations for Rseries, but we need full IV curve for Part 3 anyway, so we will calcualte the IV curve (rather than just power) for every hour of the year
# idx is the looping index for calcualting the IV curve
for idx,JLm in enumerate(JL_module): # Make a for loop; idx is indexing parameter for hours of the year, JLm is light generated current for the hour that we are calcualting
    Voc = pv.cell.Voc(JLm, J0) # Calculate Voc for one hour in the year
    voltage = np.linspace(0, Voc, 300) # Define 100 voltages to make an IV curve, going from V= 0 to V=v Voc for one hour of the year
    current = pv.cell.I_cell(voltage, JLm, J0) # Calculate current for those 100 voltage points
    voltage_r = voltage - current * Rseries #  Calculate voltage impacted by Series Resistance for each of the 100 points in the IV curve
    Voc_r, Jsc_r, FF_r, Vmp_r, Jmp_r = pv.cell.cell_params(voltage_r, current) # Extract IV curve parameters for the one hour of the year
    P_module[idx]=Vmp_r*Jmp_r*10  # Put the power from the module from that hour into an array called P_module. We ultiply by 1e4 to convert from W/cm² to W/m² and divide by 1e3 to convert to kW/m² from W/² and 

P_yearly = sum(DNI+DHI)/1e3  # Sum the total energy form the sun over the year. We divide by 1e3 to convert to kWh/m² from Wh/m²
P_yearly_module = sum(P_module) # kWh/²  Sum of energy from the module over the year. 

efficiency = 1e5*P_module/((DNI+DHI)+ 0.00000001)  # we add a small value to solar radiation so we don't divide by zero in calculating efficiency

E_sun_kWh_m2    = np.sum(DNI + DHI) / 1000.0    # kWh/m^2 over the year (TMY Wh/m^2 ÷ 1000)
E_module_kWh_m2 = np.sum(P_module)              # kWh/m^2 over the year from IV solution

# Report per m^2 metrics (requested)
print('\nSUMMARY FOR PART 1.d:')
print('Energy from Sun over year: {:.2f} kWh/m²'.format(E_sun_kWh_m2))
print('Energy from Module over year: {:.2f} kWh/m²'.format(E_module_kWh_m2))
eta_avg = 100.0 * (E_module_kWh_m2 / (E_sun_kWh_m2 + 1e-12))
print('Average Efficiency: {:.2f}%'.format(eta_avg))

# Also print kWh from the IDEAL 72-cell module (no packing factor; ideal sum of cell areas)
module_area_m2 = (Area * 72) / 1e4   # cm^2 → m^2, 72 cells in series; ideal matched module area (no gaps)
E_module_kWh = E_module_kWh_m2 * module_area_m2
print('Ideal 72-cell module energy over year (no packaging losses): {:.2f} kWh'.format(E_module_kWh))


# ************************************************************
# Project 3 Part 2 Mismatch losses in modules
# This is a repeat of Part 3.1 but now including shading in the calculation of the IV curve

print('******************* Starting Part 2 mismatch losses *****************')

# ----- Part 2 constants / inputs -----
shading = 0.50            # fraction for the ONE shaded cell (can vary later)
number_series = 8         # number of UNSHADED cells in series (plus 1 shaded -> 9 total)
number_points = 400       # resolution of each IV curve
Vbr = -5.0                # reverse-bias breakdown voltage of shaded cell (assignment: 5 V)
Vf_bp = 0.5               # bypass diode "turn-on" forward drop (approx clamp at -0.5 V)

# ----- Helpers for Part 2 (fixed current-axis alignment) -----
def iv_series_8plus1(JL_unshaded, JL_one_shaded, J0, Rseries, Vbr,
                     clamp_bypass=None, number_points=400):
    """
    Build the combined IV of 8 unshaded cells + 1 shaded cell in series.
    Both branches are evaluated on the SAME current axis: 0 -> JL_unshaded.
    - Unshaded branch: diode eqn with Rs, forward only on this axis.
    - Shaded branch: forward for I <= JL_shaded; reverse-bias for I > JL_shaded,
      clamped to Vbr (e.g., -5.0 V). If clamp_bypass is not None, clamp the shaded
      branch further to that value (e.g., -0.5 V) to emulate a bypass diode.
    Returns (current_array, v_total, Voc, Jsc, FF, Vmp, Jmp, v_u, v_s).
    """
    # Series string current axis (A/cm^2): must span up to the unshaded J
    current = np.linspace(0.0, JL_unshaded, number_points)  # A/cm^2

    # ---- Unshaded single-cell IV on this current axis ----
    # ideal diode relation in the same style as the provided example
    v_ideal_u = 0.0248 * np.log(np.maximum((JL_unshaded - 0.99999999999*current)/J0, 1e-300))
    v_u = v_ideal_u - current * Rseries

    # ---- Shaded single-cell IV on the SAME current axis ----
    # forward region: I <= JL_shaded -> use diode eqn with Rs on (JL_shaded - I)
    forward_mask = current <= JL_one_shaded
    I_forw = JL_one_shaded - current
    I_forw = np.maximum(I_forw, 1e-30)
    v_pos   = 0.0248 * np.log((I_forw / J0) + 1.0)
    v_pos_r = v_pos - I_forw * Rseries

    # reverse region: I > JL_shaded -> clamp to breakdown Vbr
    v_s = np.where(forward_mask, v_pos_r, Vbr)

    # optional bypass clamp (e.g., -0.5 V) — limit reverse excursion to no more negative than -Vf
    if clamp_bypass is not None:
        v_s = np.maximum(v_s, clamp_bypass)  # e.g., clamp to -0.5 V

    # ---- Total series voltage for 8 unshaded + 1 shaded ----
    v_total = number_series * v_u + v_s

    # Extract IV parameters of the SERIES group on this (V,I) curve
    Voc_tot, Jsc_tot, FF_tot, Vmp_tot, Jmp_tot = pv.cell.cell_params(v_total, current)

    return current, v_total, Voc_tot, Jsc_tot, FF_tot, Vmp_tot, Jmp_tot, v_u, v_s

# ===== Part 2.1: 8 unshaded + 1 shaded, NO bypass =====
JL_unshaded = JL                 # use AM1.5G cell J for the shape
JL_one_shaded = shading * JL     # shaded-cell J

current_p21, v_total_p21, Voc_t1, Jsc_t1, FF_t1, Vmp_t1, Jmp_t1, v_u1, v_s1 = iv_series_8plus1(
    JL_unshaded, JL_one_shaded, J0, Rseries, Vbr, clamp_bypass=None, number_points=number_points
)

# Overlay: unshaded cell IV, shaded cell IV, combined series IV (all in A/cm^2 vs V)
plt.figure()
plt.plot(v_u1, current_p21, label='Unshaded cell IV')
plt.plot(v_s1, current_p21, label='Shaded cell IV')
plt.plot(v_total_p21, current_p21, label='Series (8 unshaded + 1 shaded)')
plt.xlabel('Voltage (V)')
plt.ylabel('Current Density (A/cm²)')
plt.legend(); plt.ylim(0); plt.xlim(min(v_total_p21.min(), v_s1.min(), v_u1.min()) - 0.2)
plt.title('Part 2.1: IV curves (no bypass)')
plt.show()

# Separate plot: IV and Power, with MPP marked
plt.figure()
plt.plot(v_total_p21, current_p21, label='Series IV')
plt.scatter(Vmp_t1, Jmp_t1, label='MPP', zorder=3)
plt.text(Vmp_t1, Jmp_t1, '  MPP', va='bottom')
plt.xlabel('Voltage (V)')
plt.ylabel('Current Density (A/cm²)')
plt.ylim(0)
plt.twinx()
plt.plot(v_total_p21, v_total_p21 * current_p21, label='Power', alpha=0.8)
plt.ylabel('Power Density (W/cm²)')
plt.title('Part 2.1: Series IV and Power (no bypass)')
plt.show()

# ===== Part 2.2: Same grouping but WITH bypass diode (clamp shaded branch at ~ -Vf) =====
current_p22, v_total_p22, Voc_t2, Jsc_t2, FF_t2, Vmp_t2, Jmp_t2, v_u2, v_s2 = iv_series_8plus1(
    JL_unshaded, JL_one_shaded, J0, Rseries, Vbr, clamp_bypass=-Vf_bp, number_points=number_points
)

# Overlay IVs
plt.figure()
plt.plot(v_u2, current_p22, label='Unshaded cell IV')
plt.plot(v_s2, current_p22, label='Shaded cell IV (bypass clamp)')
plt.plot(v_total_p22, current_p22, label='Series (8+1 with bypass)')
plt.xlabel('Voltage (V)')
plt.ylabel('Current Density (A/cm²)')
plt.legend(); plt.ylim(0); plt.xlim(min(v_total_p22.min(), v_s2.min(), v_u2.min()) - 0.2)
plt.title('Part 2.2: IV curves (with bypass diode)')
plt.show()

# IV + Power + MPP
plt.figure()
plt.plot(v_total_p22, current_p22, label='Series IV (with bypass)')
plt.scatter(Vmp_t2, Jmp_t2, label='MPP', zorder=3)
plt.text(Vmp_t2, Jmp_t2, '  MPP', va='bottom')
plt.xlabel('Voltage (V)')
plt.ylabel('Current Density (A/cm²)')
plt.ylim(0)
plt.twinx()
plt.plot(v_total_p22, v_total_p22 * current_p22, label='Power', alpha=0.8)
plt.ylabel('Power Density (W/cm²)')
plt.title('Part 2.2: Series IV and Power (with bypass)')
plt.show()

# ---- Yearly energy with CONSTANT shading fraction on one cell, including bypass ----
# For each hour, use JL_unshaded = JL_module[idx], shaded = shading * JL_module[idx]
P_mismatch_bp = np.zeros_like(JL_module)  # kWh/m^2 per hour
for i, JLm in enumerate(JL_module):
    cur_i, v_tot_i, Vo_i, Js_i, FF_i, Vmp_i, Jmp_i, _, _ = iv_series_8plus1(
        JLm, shading * JLm, J0, Rseries, Vbr, clamp_bypass=-Vf_bp, number_points=200
    )
    # power density at MPP: W/cm^2 -> kW/m^2 (×10)
    P_mismatch_bp[i] = Vmp_i * Jmp_i * 10.0

E_year_bp_kWh_m2 = np.sum(P_mismatch_bp)
module_area_m2 = (Area * 72) / 1e4
E_year_bp_kWh = E_year_bp_kWh_m2 * module_area_m2

print(f"Part 2.2: Total energy (with bypass, constant shaded cell {shading:.2f}) = {E_year_bp_kWh_m2:.2f} kWh/m²,  {E_year_bp_kWh:.2f} kWh (module)")

# ===== Part 2.3: 50% shading from 8–11 AM every day (hours 8,9,10,11 local) =====
P_mismatch_time = np.zeros_like(JL_module)  # kWh/m^2 per hour

for idx, JLm in enumerate(JL_module):
    hour_of_day = idx % 24
    # 8,9,10,11 → shaded; else unshaded
    shade_now = 0.5 if (8 <= hour_of_day <= 11) else 0.0
    cur_i, v_tot_i, Vo_i, Js_i, FF_i, Vmp_i, Jmp_i, _, _ = iv_series_8plus1(
        JLm, shade_now * JLm, J0, Rseries, Vbr, clamp_bypass=-Vf_bp, number_points=200
    )
    P_mismatch_time[idx] = Vmp_i * Jmp_i * 10.0

E_year_time_kWh_m2 = np.sum(P_mismatch_time)
E_year_time_kWh    = E_year_time_kWh_m2 * module_area_m2

print(f"Part 2.3: Total energy with 50% shading 8–11 AM (with bypass) = {E_year_time_kWh_m2:.2f} kWh/m²,  {E_year_time_kWh:.2f} kWh (module)")

# ===== Part 2.4: Compare uniform reduced-intensity vs. series-mismatch shading =====
# Build a uniformly reduced-intensity JL time series (0.5× during 8–11 AM for ALL cells)
JL_uniform = JL_module.copy()
for idx in range(len(JL_uniform)):
    if 8 <= (idx % 24) <= 11:
        JL_uniform[idx] *= 0.5

# Compute hourly power density with the standard Part 1(d) method (no mismatch, just uniform JL)
P_uniform = np.zeros_like(JL_uniform)
for i, JLm in enumerate(JL_uniform):
    Voc = pv.cell.Voc(JLm, J0)
    voltage = np.linspace(0, Voc, 300)
    current = pv.cell.I_cell(voltage, JLm, J0)
    voltage_r = voltage - current * Rseries
    Voc_r, Jsc_r, FF_r, Vmp_r, Jmp_r = pv.cell.cell_params(voltage_r, current)
    P_uniform[i] = Vmp_r * Jmp_r * 10.0

E_uniform_kWh_m2 = np.sum(P_uniform)
E_uniform_kWh    = E_uniform_kWh_m2 * module_area_m2

print(f"Part 2.4: Total energy with UNIFORM 0.5× intensity 8–11 AM = {E_uniform_kWh_m2:.2f} kWh/m²,  {E_uniform_kWh:.2f} kWh (module)")

# Ratio of uniform-intensity energy to the series-mismatch case (Part 2.3)
ratio_uniform_to_mismatch = E_uniform_kWh / (E_year_time_kWh + 1e-12)
print(f"Part 2.4: Ratio (Uniform / Series-Mismatch) = {ratio_uniform_to_mismatch:.3f}")
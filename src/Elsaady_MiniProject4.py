"""
Mini Project 4: PV System Analysis for Monument Valley, AZ
EEE 465/591: Photovoltaic Energy Conversion

System: Two 285W modules (0.57 kW), 30° tilt, due south
Location: Monument Valley, AZ (TMY: Page, AZ - 723710TYA.CSV)
Battery: Li-ion 48V, 72 Ah
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================================
# SECTION 1: HELPER FUNCTIONS (from provided snippets)
# ============================================================================

def sind(angle):
    """Return the sine of the angle (degrees)"""
    return np.sin(np.radians(angle))

def cosd(angle):
    """Return the cosine of the angle (degrees)"""
    return np.cos(np.radians(angle))

def tand(angle):
    """Return the tangent of the angle (degrees)"""
    return np.tan(np.radians(angle))

def arcsind(x):
    """Return the arcsin (degrees)"""
    return np.degrees(np.arcsin(x))

def arccosd(x):
    """Return the arccos (degrees)"""
    return np.degrees(np.arccos(x))

def declination(day_no):
    """Return declination angle of sun (degrees) where day_no is the day of the year.
    For Jan 1 day_no = 1, Dec 31 day_no = 365. No correction for leap years"""
    return 23.45 * sind((day_no - 81) * (360 / 365))

def sun_rise_set(latitude, declination, time_correction):
    """Return the sunrise and sunset times in hours
    given the latitude (degrees) and the declination (degrees)"""
    A = -1 * (sind(latitude) * sind(declination)) / (cosd(latitude) * cosd(declination))
    local_solar_time = arccosd(A) / 15.0
    sunrise = 12.0 - local_solar_time - (time_correction / 60.0)
    sunset = 12 + local_solar_time - (time_correction / 60.0)
    return sunrise, sunset

# ============================================================================
# SECTION 2: PV MODULE IV CURVE FUNCTIONS (from MP3 pattern)
# ============================================================================

def Voc(JL, J0, Vt=0.0248):
    """Calculate open circuit voltage"""
    return Vt * np.log(JL / J0 + 1)

def I_cell(V, JL, J0, Vt=0.0248):
    """Calculate cell current"""
    return JL - J0 * (np.exp(V / Vt) - 1)

def cell_params(voltage, current):
    """Extract cell parameters from IV curve"""
    power = voltage * current
    max_idx = np.argmax(power)
    Pmp = power[max_idx]
    Vmp = voltage[max_idx]
    Jmp = current[max_idx]
    Voc_val = voltage[-1]
    Jsc_val = current[0]
    FF = Pmp / (Voc_val * Jsc_val) if (Voc_val * Jsc_val) > 0 else 0
    return Voc_val, Jsc_val, FF, Vmp, Jmp, Pmp

# ============================================================================
# SECTION 3: READ TMY DATA
# ============================================================================

print("="*70)
print("MINI PROJECT 4: PV SYSTEM ANALYSIS")
print("="*70)
print("\nLoading TMY data from 723710TYA.CSV...")

# Read TMY data
tmy_data = pd.read_csv('723710TYA.CSV', skiprows=1)

# Extract required columns
GHI = tmy_data['GHI (W/m^2)'].values  # Global Horizontal Irradiance
DNI = tmy_data['DNI (W/m^2)'].values  # Direct Normal Irradiance
DHI = tmy_data['DHI (W/m^2)'].values  # Diffuse Horizontal Irradiance
Tdry = tmy_data['Dry-bulb (C)'].values    # Dry bulb temperature

# Location parameters (Page, AZ)
latitude = 36.9  # degrees
longitude = -111.4  # degrees

print(f"Data loaded: {len(GHI)} hours")
print(f"Location: Monument Valley, AZ (TMY: Page, AZ)")
print(f"Latitude: {latitude}°, Longitude: {longitude}°")

# ============================================================================
# SECTION 4: CALCULATE TILTED IRRADIANCE
# ============================================================================

print("\nCalculating tilted irradiance (30° tilt, due south)...")

# Module parameters
tilt_angle = 30  # degrees from horizontal
surface_azimuth = 180  # due south

# Calculate tilted plane irradiance for each hour
tilted_irradiance = np.zeros(len(GHI))

for idx in range(len(GHI)):
    day_number = idx // 24 + 1
    hour = idx - (day_number - 1) * 24
    
    # Solar geometry
    dec = declination(day_number)
    hour_angle = (hour - 12) * 15  # degrees
    
    # Solar position
    sin_altitude = (sind(latitude) * sind(dec) + 
                   cosd(latitude) * cosd(dec) * cosd(hour_angle))
    
    if sin_altitude > 0:
        altitude = arcsind(sin_altitude)
        cos_zenith = sin_altitude
        
        # --- Solar azimuth (degrees) ---
        # Use robust formulas tied to MP1-style geometry
        # hour_angle in degrees; convert to radians when used in trig
        # Compute sine and cosine of azimuth via standard relations:
        # sin(γs) = (cos δ * sin ω) / cos α
        # cos(γs) = (sin δ * cos φ - cos δ * sin φ * cos ω) / cos α
        cos_alpha = np.sqrt(max(0.0, 1.0 - sin_altitude**2))  # cos(altitude)
        sin_gamma = (cosd(dec) * sind(hour_angle)) / max(cos_alpha, 1e-12)
        cos_gamma = ((sind(dec) * cosd(latitude) - cosd(dec) * sind(latitude) * cosd(hour_angle))
                     / max(cos_alpha, 1e-12))
        gamma_s = np.degrees(np.arctan2(sin_gamma, cos_gamma))  # solar azimuth, degrees

        # --- Incidence on tilted plane (MP1 pattern) ---
        # cos θ = sin α cos β + cos α sin β cos(γs − γsurface)
        cos_theta = (sind(altitude) * cosd(tilt_angle) + 
                     cos_alpha * sind(tilt_angle) * cosd(gamma_s - surface_azimuth))
        
        if cos_theta > 0:
            # Tilted irradiance components
            beam_tilted = DNI[idx] * cos_theta
            diffuse_tilted = DHI[idx] * (1 + cosd(tilt_angle)) / 2
            ground_reflected = GHI[idx] * 0.2 * (1 - cosd(tilt_angle)) / 2
            
            tilted_irradiance[idx] = beam_tilted + diffuse_tilted + ground_reflected
        else:
            tilted_irradiance[idx] = 0
    else:
        tilted_irradiance[idx] = 0

# ============================================================================
# SECTION 5: CALCULATE PV MODULE ENERGY (IV CURVES AT EVERY HOUR)
# ============================================================================

print("\nCalculating hourly PV module energy using IV curves...")

# Module specifications (two 285W modules in series)
# Single module: Vmp ~36.5V, Imp ~7.8A, Voc ~44.5V, Isc ~8.4A
# Two modules in series: Vmp ~73V, Imp ~7.8A, Voc ~89V
module_area = 1.94  # m² per module (from MP4 table)
total_area = 2 * module_area  # two modules

# Cell parameters (from MP3 absorbed code)
JL_ref = 0.0379639368734       # A/cm² at AM1.5G
J0 = 2.27207184075e-13         # A/cm²
Rseries = 0.6935010143333081   # Ω·cm² (series resistance per MP3)
Vt = 0.0248                    # V (kT/q used in MP3 diode relations)

# Arrays for hourly energy
P_module = np.zeros(len(tilted_irradiance))  # kW
JL_module = np.zeros(len(tilted_irradiance))

# Calculate IV curve for every hour
for idx, irrad in enumerate(tilted_irradiance):
    # Scale light-generated current by irradiance (reference 1000 W/m²)
    JLm = JL_ref * (irrad / 1000.0)
    JL_module[idx] = JLm
    
    if JLm > 1e-6:  # Only calculate if there's sunlight
        Voc_val = Voc(JLm, J0, Vt)
        voltage = np.linspace(0, Voc_val, 100)
        current = I_cell(voltage, JLm, J0, Vt)
        voltage_r = voltage - current * Rseries
        Voc_r, Jsc_r, FF_r, Vmp_r, Jmp_r, Pmp_r = cell_params(voltage_r, current)
        
        # Convert to module power: W/cm² to kW for module area
        P_module[idx] = Pmp_r * 10  # Convert to kW/m²

# Calculate energy in Wh (power in kW * 1 hour * 1000 to get Wh)
PV_Array_Wh = P_module * 1000 * total_area  # Wh per hour

# Convert Wh to Ah using assignment formula: Ah = Wh / V
# V = 48V nominal system voltage (per assignment spec)
system_voltage = 48  # V (nominal system voltage per MP4 handout)
PV_Array_Ah = PV_Array_Wh / system_voltage  # Ah per hour

annual_pv_kwh = np.sum(PV_Array_Wh) / 1000  # Total kWh
annual_pv_ah = np.sum(PV_Array_Ah)  # Total Ah

print(f"Annual PV generation: {annual_pv_kwh:.2f} kWh, {annual_pv_ah:.2f} Ah")

# ============================================================================
# SECTION 6: CALCULATE HOURLY LOADS
# ============================================================================

print("\nCalculating hourly loads...")

# Load specifications (from assignment)
# Lighting: 4 LED lights at 4W each = 16W DC
# Additional lighting: LED shop light 24W DC
# Inverter loads (converted to DC equivalent at 95% efficiency):
#   - Screen: 20W / 0.95 = 21.05W
#   - Laptop: 30W / 0.95 = 31.58W
#   - Freezer: 95W / 0.95 = 100W

inverter_efficiency = 0.95

# Initialize load arrays
Load_Wh = np.zeros(len(PV_Array_Ah))
rise_plot = np.zeros_like(PV_Array_Ah)
set_plot = np.zeros_like(PV_Array_Ah)

# NEW: load components (Wh)
Light16_Wh    = np.zeros(len(PV_Array_Ah))  # 4×4 W LEDs
Shop24_Wh     = np.zeros(len(PV_Array_Ah))  # shop light
ScreenLap_Wh  = np.zeros(len(PV_Array_Ah))  # screen + laptop (DC equivalent)
Freezer_Wh    = np.zeros(len(PV_Array_Ah))  # freezer (DC equivalent)

for idx in range(len(PV_Array_Ah)):
    day_number = idx // 24 + 1
    hour = idx - (day_number - 1) * 24
    
    # Sunrise/sunset
    dec = declination(day_number)
    sunrise, sunset = sun_rise_set(latitude, dec, 0)
    rise_plot[idx] = sunrise
    set_plot[idx]  = sunset

    # Components (Wh)
    light1    = 16 if ((hour >= sunset - 2) and (hour < 22)) else 0
    shop      = 24 if (19 <= hour < 22) else 0
    screenlap = ((20 + 30) / inverter_efficiency) if (19 <= hour < 22) else 0
    freezer   = (95 / inverter_efficiency) if (hour % 4 == 0) else 0

    # Save components
    Light16_Wh[idx]   = light1
    Shop24_Wh[idx]    = shop
    ScreenLap_Wh[idx] = screenlap
    Freezer_Wh[idx]   = freezer

    # Total hourly load (Wh)
    Load_Wh[idx] = light1 + shop + screenlap + freezer

# Convert Load Wh to Ah using assignment formula: Ah = Wh / V (V = 48V)
Load = Load_Wh / system_voltage  # Ah per hour

annual_load_kwh = np.sum(Load_Wh) / 1000  # Total kWh
annual_load_ah = np.sum(Load)  # Total Ah

print(f"Annual load: {annual_load_kwh:.2f} kWh, {annual_load_ah:.2f} Ah")

# ============================================================================
# SECTION 7: ENERGY ROUTING & BATTERY STATE (from snippet A)
# ============================================================================

print("\nCalculating energy routing and battery state of charge...")

# Battery Parameters (from assignment: Li-ion 48V, 72Ah)
capacity = 72  # battery capacity in Ah
DOD = 0.3  # Depth of discharge (from snippet A)

# Initialize PV system state parameters
BSOC = np.zeros(len(PV_Array_Ah) + 1)  # Battery state of charge (fraction)
BSOC[0] = 1.0  # Start with battery fully charged
battery_to_load = np.zeros(len(PV_Array_Ah))  # Ah from battery to load

# Calculate PV to Load (from snippet A)
PV_to_load = np.minimum(PV_Array_Ah, Load)

# Calculate BSOC and battery to load (from snippet A logic)
for idx, PV_Ah in enumerate(PV_Array_Ah):
    if PV_Ah >= Load[idx]:
        # Extra Ah after supplying load goes TO the battery
        BSOC[idx + 1] = np.minimum(BSOC[idx] + (PV_Ah - PV_to_load[idx]) / capacity, 1.0)
    else:
        # Battery supplies the remainder if there is enough capacity
        battery_to_load[idx] = np.minimum(Load[idx] - PV_Ah, (BSOC[idx] - DOD) * capacity)
        BSOC[idx + 1] = np.maximum(BSOC[idx] - ((Load[idx] - PV_to_load[idx]) / capacity), DOD)

# Resize BSOC to get rid of the one extra data point
BSOC = np.resize(BSOC, 8760)

# Calculate other routing parameters
PV_to_battery = np.minimum(PV_Array_Ah - PV_to_load, (1 - BSOC) * capacity)
PV_unused = PV_Array_Ah - PV_to_load - PV_to_battery
load_unmet = np.maximum((Load - PV_Array_Ah - battery_to_load), 0)

# ============================================================================
# SECTION 8: PART 2 ANALYSIS - CALCULATE KPIs
# ============================================================================

print("\nCalculating system performance metrics...")

# Availability (from snippet A formula)
availability = (np.sum(Load) - np.sum(load_unmet)) / np.sum(Load)

# Battery statistics
avg_bsoc = np.mean(BSOC)
min_bsoc = np.min(BSOC)
min_bsoc_hour = np.argmin(BSOC)
min_bsoc_day = int(min_bsoc_hour / 24)

# Solar energy utilization (from snippet A formulas)
fraction_used_solar = (np.sum(PV_Array_Ah) - np.sum(PV_unused)) / np.sum(PV_Array_Ah)
fraction_unused_solar = np.sum(PV_unused) / np.sum(PV_Array_Ah)

# Ratio of energy to load vs generated (from assignment Part 2.3)
energy_to_load = np.sum(PV_to_load) + np.sum(battery_to_load)  # Total Ah to load
energy_generated = np.sum(PV_Array_Ah)  # Total Ah generated
ratio_load_to_generated = energy_to_load / energy_generated

# Energy-based ratio (Part 2.3) in Wh
# Powered load in Wh = requested load - unmet load (both in Wh)
unmet_Wh = load_unmet * system_voltage
powered_load_Wh = Load_Wh - unmet_Wh
ratio_load_to_generated_Wh = (np.sum(powered_load_Wh) / np.sum(PV_Array_Wh)
                              if np.sum(PV_Array_Wh) > 0 else 0.0)

# Prepare P/N/S flows in Wh for plotting
PV_to_load_Wh      = PV_to_load * system_voltage   # P
battery_to_load_Wh = battery_to_load * system_voltage  # S
load_unmet_Wh      = load_unmet * system_voltage   # N

# ============================================================================
# SECTION 9: PLOTS (clean + P/N/S separated)
# ============================================================================

print("\nGenerating plots...")

def rolling(arr, w=168):  # 7-day (168 h) centered mean
    return pd.Series(arr).rolling(window=w, min_periods=1, center=True).mean().values

hours = np.arange(len(PV_Array_Wh))

# Rolling series
PV_Array_Wh_roll = rolling(PV_Array_Wh)
PV_Array_Ah_roll = rolling(PV_Array_Ah)
Load_Wh_roll     = rolling(Load_Wh)
Load_Ah_roll     = rolling(Load)
BSOC_pct_roll    = rolling(BSOC * 100.0)
PV2bat_roll      = rolling(PV_to_battery)

# Load component rollups
Light16_roll   = rolling(Light16_Wh)
Shop24_roll    = rolling(Shop24_Wh)
ScreenLap_roll = rolling(ScreenLap_Wh)
Freezer_roll   = rolling(Freezer_Wh)

# ---------- Individual Figures (6 separate plots) ----------
hourly_lw, hourly_a = 0.25, 0.25
smooth_lw, smooth_a = 1.4, 1.0

# Plot 1: PV Energy (Wh)
fig1 = plt.figure(figsize=(12, 6), dpi=150)
ax1 = fig1.add_subplot(1, 1, 1)
ax1.plot(hours, PV_Array_Wh, linewidth=hourly_lw, alpha=hourly_a)
ax1.plot(hours, PV_Array_Wh_roll, linewidth=smooth_lw, alpha=smooth_a)
ax1.set_xlabel('Hour of Year'); ax1.set_ylabel('PV Energy (Wh)')
ax1.set_title('PV Module Energy Output (Wh)\n'
              'Monument Valley AZ, 30° tilt, due south, 0.57 kW nameplate\n'
              f'Annual total: {annual_pv_kwh:.2f} kWh')
ax1.grid(True, alpha=0.25); ax1.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_1_PV_Energy_Wh.png', dpi=300, bbox_inches='tight')
print("Plot 1 saved as 'MP4_1_PV_Energy_Wh.png'")
plt.show()
plt.close(fig1)

# Plot 2: PV Ah
fig2 = plt.figure(figsize=(12, 6), dpi=150)
ax2 = fig2.add_subplot(1, 1, 1)
ax2.plot(hours, PV_Array_Ah, linewidth=hourly_lw, alpha=hourly_a)
ax2.plot(hours, PV_Array_Ah_roll, linewidth=smooth_lw, alpha=smooth_a)
ax2.set_xlabel('Hour of Year'); ax2.set_ylabel('PV Current (Ah)')
ax2.set_title(f'PV Module Current Output (Ah)\nAnnual total: {annual_pv_ah:.2f} Ah')
ax2.grid(True, alpha=0.25); ax2.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_2_PV_Current_Ah.png', dpi=300, bbox_inches='tight')
print("Plot 2 saved as 'MP4_2_PV_Current_Ah.png'")
plt.show()
plt.close(fig2)

# Plot 3: Load components (stacked, smoothed)
fig3 = plt.figure(figsize=(12, 6), dpi=150)
ax3 = fig3.add_subplot(1, 1, 1)
ax3.stackplot(hours,
              Light16_roll, Shop24_roll, ScreenLap_roll, Freezer_roll,
              labels=['LEDs 16W', 'Shop 24W', 'Screen+Laptop (DC eq.)', 'Freezer (DC eq.)'],
              alpha=0.9)
ax3.set_xlabel('Hour of Year'); ax3.set_ylabel('Load (Wh)')
ax3.set_title(f'Hourly Load Components (7-day mean)\nAnnual total: {annual_load_kwh:.2f} kWh')
ax3.legend(loc='upper right', ncol=2, fontsize=10, framealpha=0.9)
ax3.grid(True, alpha=0.25); ax3.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_3_Load_Components_Wh.png', dpi=300, bbox_inches='tight')
print("Plot 3 saved as 'MP4_3_Load_Components_Wh.png'")
plt.show()
plt.close(fig3)

# Plot 4: Total Load (Ah)
fig4 = plt.figure(figsize=(12, 6), dpi=150)
ax4 = fig4.add_subplot(1, 1, 1)
ax4.plot(hours, Load, linewidth=hourly_lw, alpha=hourly_a, color='red')
ax4.plot(hours, Load_Ah_roll, linewidth=smooth_lw, alpha=smooth_a, color='red')
ax4.set_xlabel('Hour of Year'); ax4.set_ylabel('Load (Ah)')
ax4.set_title(f'Hourly Load Profile (Ah)\nAnnual total: {annual_load_ah:.2f} Ah')
ax4.grid(True, alpha=0.25); ax4.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_4_Load_Total_Ah.png', dpi=300, bbox_inches='tight')
print("Plot 4 saved as 'MP4_4_Load_Total_Ah.png'")
plt.show()
plt.close(fig4)

# Plot 5: Battery SOC
fig5 = plt.figure(figsize=(12, 6), dpi=150)
ax5 = fig5.add_subplot(1, 1, 1)
ax5.plot(hours, BSOC * 100.0, linewidth=hourly_lw, alpha=hourly_a, color='purple')
ax5.plot(hours, BSOC_pct_roll, linewidth=smooth_lw, alpha=smooth_a, color='purple')
ax5.axhline(y=DOD * 100, color='r', linestyle='--', label=f'DOD = {DOD*100:.0f}%')
ax5.set_xlabel('Hour of Year'); ax5.set_ylabel('Battery SOC (%)')
ax5.set_title('Battery State of Charge\n'
              f'Avg: {avg_bsoc*100:.1f}%, Min: {min_bsoc*100:.1f}% at hour {min_bsoc_hour}')
ax5.legend(); ax5.grid(True, alpha=0.25); ax5.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_5_Battery_SOC.png', dpi=300, bbox_inches='tight')
print("Plot 5 saved as 'MP4_5_Battery_SOC.png'")
plt.show()
plt.close(fig5)

# Plot 6: PV -> Battery (Ah)
fig6 = plt.figure(figsize=(12, 6), dpi=150)
ax6 = fig6.add_subplot(1, 1, 1)
ax6.plot(hours, PV_to_battery, linewidth=hourly_lw, alpha=hourly_a, color='brown')
ax6.plot(hours, PV2bat_roll, linewidth=smooth_lw, alpha=smooth_a, color='brown')
ax6.set_xlabel('Hour of Year'); ax6.set_ylabel('PV to Battery (Ah)')
ax6.set_title(f'PV Energy to Battery\nTotal: {np.sum(PV_to_battery):.2f} Ah')
ax6.grid(True, alpha=0.25); ax6.margins(x=0)
plt.tight_layout()
plt.savefig('MP4_6_PV_to_Battery.png', dpi=300, bbox_inches='tight')
print("Plot 6 saved as 'MP4_6_PV_to_Battery.png'")
plt.show()
plt.close(fig6)

# ---------- P / N / S flows (separated) ----------
fig_pns = plt.figure(figsize=(18, 8), dpi=150)

P_roll = rolling(PV_to_load_Wh)
N_roll = rolling(load_unmet_Wh)
S_roll = rolling(battery_to_load_Wh)

# P: PV -> Load
axP = fig_pns.add_subplot(3, 1, 1)
axP.plot(hours, PV_to_load_Wh, linewidth=hourly_lw, alpha=hourly_a)
axP.plot(hours, P_roll, linewidth=smooth_lw, alpha=smooth_a)
axP.set_ylabel('P: PV → Load (Wh)')
axP.set_title(f'P / N / S Flows (Hourly thin + 7-day mean)  |  '
              f'ΣP={np.sum(PV_to_load_Wh):.0f} Wh, ΣN={np.sum(load_unmet_Wh):.0f} Wh, '
              f'ΣS={np.sum(battery_to_load_Wh):.0f} Wh')
axP.grid(True, alpha=0.25); axP.margins(x=0)

# N: Not-served (unmet) load
axN = fig_pns.add_subplot(3, 1, 2, sharex=axP)
axN.plot(hours, load_unmet_Wh, linewidth=hourly_lw, alpha=hourly_a, color='tab:red')
axN.plot(hours, N_roll, linewidth=smooth_lw, alpha=smooth_a, color='tab:red')
axN.set_ylabel('N: Not-served (Wh)')
axN.grid(True, alpha=0.25); axN.margins(x=0)

# S: Storage -> Load
axS = fig_pns.add_subplot(3, 1, 3, sharex=axP)
axS.plot(hours, battery_to_load_Wh, linewidth=hourly_lw, alpha=hourly_a, color='tab:green')
axS.plot(hours, S_roll, linewidth=smooth_lw, alpha=smooth_a, color='tab:green')
axS.set_ylabel('S: Storage → Load (Wh)'); axS.set_xlabel('Hour of Year')
axS.grid(True, alpha=0.25); axS.margins(x=0)

plt.tight_layout()
plt.savefig('MP4_7_PNS_flows.png', dpi=300, bbox_inches='tight')
print("Plot 7 saved as 'MP4_7_PNS_flows.png'")
plt.show()
plt.close(fig_pns)

# ============================================================================
# SECTION 10: CONSOLE SUMMARY (PART 1 & PART 2 OUTPUTS)
# ============================================================================

print("\n" + "="*70)
print("MINI PROJECT 4 RESULTS SUMMARY")
print("="*70)

print("\n--- PART 1: System Parameters ---")
print(f"\nAnnual PV Generation:")
print(f"  Total Energy: {annual_pv_kwh:.2f} kWh")
print(f"  Total Current: {annual_pv_ah:.2f} Ah")

print(f"\nAnnual Load:")
print(f"  Total Energy: {annual_load_kwh:.2f} kWh")
print(f"  Total Current: {annual_load_ah:.2f} Ah")

print("\n--- PART 2: System Analysis ---")
print(f"\n1. System Availability: {availability*100:.2f}%")
print(f"   (Ratio of powered load to requested load)")

print(f"\n2. Battery State of Charge:")
print(f"   Average BSOC: {avg_bsoc*100:.2f}%")
print(f"   Minimum BSOC: {min_bsoc*100:.2f}%")
print(f"   Minimum occurs at: Hour {min_bsoc_hour} (Day {min_bsoc_day+1})")

print(f"\n3. Energy Utilization:")
print(f"   Ratio (Energy to Load / Energy Generated) [Wh]: {ratio_load_to_generated_Wh:.4f}")
print(f"   Ratio (Energy to Load / Energy Generated) [Ah]: {ratio_load_to_generated:.4f}")
print(f"   Fraction of PV energy used: {fraction_used_solar*100:.2f}%")
print(f"   Fraction of PV energy unused: {fraction_unused_solar*100:.2f}%")

print(f"\n4. Energy Flow Summary:")
print(f"   PV to Load: {np.sum(PV_to_load):.2f} Ah")
print(f"   PV to Battery: {np.sum(PV_to_battery):.2f} Ah")
print(f"   PV Unused: {np.sum(PV_unused):.2f} Ah")
print(f"   Battery to Load: {np.sum(battery_to_load):.2f} Ah")
print(f"   Load Unmet: {np.sum(load_unmet):.2f} Ah")

print("\n" + "="*70)
print("Analysis complete!")
print("="*70)
print("\nSeven separate image files generated:")
print("  1. MP4_1_PV_Energy_Wh.png - PV Energy Output")
print("  2. MP4_2_PV_Current_Ah.png - PV Current Output")
print("  3. MP4_3_Load_Components_Wh.png - Load Components (Stacked)")
print("  4. MP4_4_Load_Total_Ah.png - Total Load")
print("  5. MP4_5_Battery_SOC.png - Battery State of Charge")
print("  6. MP4_6_PV_to_Battery.png - PV to Battery Flow")
print("  7. MP4_7_PNS_flows.png - P/N/S Energy Flows")
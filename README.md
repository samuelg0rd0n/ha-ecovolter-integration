# EcoVolter Home Assistant Integration

A Home Assistant integration for [EcoVolter II EV chargers](https://www.ecovolter.com/) that enables you to locally control basic charging functions such as turning charging on and off, setting target current, and monitoring whether your vehicle is plugged in or actively charging. It uses their [API](https://asnplus.github.io/revc-charger-local-api-documentation/).

**Only EcoVolter II (2nd generation) with local control is supported by this integration.** If you have 1st generation with cloud API using iXmanager app, you can use [iXmanager Integration](https://github.com/kubacizek/home-assistant-ixmanager).

I originally created this integration for my own use, but thought others might find it helpful as well. Enjoy! :-)

## Installation

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Settings → Repositories
   - Click the "+" button
   - Add repository: `samuelg0rd0n/ha-ecovolter-integration`
   - Category: Integration
3. Search for "EcoVolter" in HACS → Integrations
4. Click "Download" and then "Restart Home Assistant"
5. Add the integration via Settings → Devices & Services → Add Integration → Search for "EcoVolter"

### Option 2: Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/ecovolter` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services → Add Integration → Search for "EcoVolter"

## Configuration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **"EcoVolter"** and select it
4. Enter your EcoVolter charger's serial number. This can be found in the EV-Manager (iOS/Android app) or directly printed on the charger.
5. Enter your charger's secret key. By default this is the same as your serial number. As of August 2025, EcoVolter says that the option to set secret key will be added to EV-Manager in the upcoming versions.
6. If your network setup does not support mDNS, enter the charger URL.
7. You can modify the default polling interval.
8. Click **Submit**

## Features

### 🧠 Monitoring (Binary Sensors)
- **Charging Status** – Indicates whether the charger is actively charging your vehicle  
- **Vehicle Connected** – Detects if a vehicle is plugged into the charger  
- **Boost Mode Available** – Shows if boost-mode charging is currently available
- **Boost Mode Active** – Displays whether boost-mode charging is currently active  
- **3-Phase Mode Available** – Shows if 3-phase charging is available at the connected socket  
- **3-Phase Mode Active** – Indicates whether 3-phase charging is currently in use  
- **Charging Schedule Active** – Signals whether a charging schedule (calendar) is controlling the charger  

---

### ⚙️ Controls (Switches)
- **Charging Enabled** – Enables or disables charging entirely  
- **3-Phase Mode Control** – Switch between single-phase and three-phase charging  
- **Boost Mode Enabled** – Activates or deactivates boost mode  
- **Local Panel Enabled** – Enables or disables local panel (on-device) control  

---

### 🔢 Adjustable Parameters (Numbers)
- **Target Current** – Desired charging current (6–16 A)  
- **Boost Current** – Charging current during boost period (6–16 A)  
- **Maximum Current** – Upper limit for target and boost current (6–16 A)  
- **Boost Time** – Duration of the boost-current period, in seconds (up to 24 h)  
- **Energy Price** – Configurable price per kWh, used for calculating charging cost  

---

### 💱 Configuration (Selects)
- **Currency** – Selects the currency used for cost calculations  

---

### 📊 Measurements (Sensors)
- **Actual Power** – Real-time charging power (kW)  
- **Charged Energy** – Energy delivered during the current session (kWh)  
- **Charging Cost** – Calculated session cost in the selected currency  
- **Charging Time** – Elapsed time of the current charging session (seconds)  
- **Remaining Boost Time** – Remaining duration of the active boost period (seconds)  
- **Current (L1–L3)** – Measured current on each phase (A)  
- **Voltage (L1–L3)** – Voltage on each phase (V)  
- **Temperature Current Limit** – Current limit imposed by thermal protection (A)  
- **Adapter Max Current** – Maximum current allowed by the connected adapter (A)  

**Temperatures (diagnostic):** (°C)
- **Internal Temperature**
- **Adapter Temperatures** (1–3)
- **Relay Temperatures** (1–2)

---

### 📊 Lifetime monitoring (Sensors)
- **Charging Power (Max)** — Reported maximum charging power (kW)
- **Total Charged Energy** — Lifetime energy delivered (kWh)
- **Total Charging Time** — Lifetime charging time (seconds)
- **Total Charging Count** — Lifetime number of charging sessions

---

### 🛠️ Hardware / Capability (Sensors)
- **Charger Type** — Hardware capability (3×16 A or 3×32 A)
- **Charging Power (Max)** — Reported maximum charging power (kW)

## Requirements

- Home Assistant 2023.8.0 or newer
- EcoVolter II (2nd generation) EV charger with network connectivity
- Base URL (with IP address or DNS record) unless you are using mDNS in your setup

## Troubleshooting

- **Integration not found**: Make sure you've restarted Home Assistant after installation
- **Connection failed**: Verify your charger's serial number, URL and network connectivity
- **Authentication error**: Check your charger's secret key

## Support

If you encounter any issues or have questions, please:
1. Check the troubleshooting section above
2. Review the Home Assistant logs for error messages
3. Open an issue on this repository with detailed information about your setup

# EcoVolter Home Assistant Integration

A Home Assistant integration for [EcoVolter II EV chargers](https://www.ecovolter.com/) that enables you to locally control basic charging functions such as turning charging on and off, setting target current, and monitoring whether your vehicle is plugged in or actively charging. It uses their [API](https://asnplus.github.io/revc-charger-local-api-documentation/).

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
6. Click **Submit**

## Features

### Binary Sensors
- **Is Charging**: Shows whether the charger is actively charging your vehicle
- **Is Vehicle Connected**: Indicates if a vehicle is plugged into the charger
- **3-Phase Mode Enabled**: Shows the current phase mode status

### Sensors
- **Actual Power**: Real-time power consumption in watts

### Controls
- **Start/Stop Charging**: Control charging sessions
- **Set Target Current**: Adjust the charging current (6A to 16A)
- **3-Phase Mode Control**: Enable or disable 3-phase charging mode

## Requirements

- Home Assistant 2023.8.0 or newer
- EcoVolter II EV charger with network connectivity

**Only EcoVolter II (2nd version) with local control is supported by this integration.** If you have 1st version with cloud API and using iXmanager app, you can use [this integration](https://github.com/kubacizek/home-assistant-ixmanager).

## Troubleshooting

- **Integration not found**: Make sure you've restarted Home Assistant after installation
- **Connection failed**: Verify your charger's serial number and network connectivity
- **Authentication error**: Check your charger's secret key

## Support

If you encounter any issues or have questions, please:
1. Check the troubleshooting section above
2. Review the Home Assistant logs for error messages
3. Open an issue on this repository with detailed information about your setup

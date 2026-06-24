# Victron BLE D-Bus Gateway

Python gateway for Victron Energy Instant Readout BLE advertisements.

It listens for encrypted Victron BLE advertisements, decrypts them locally using the configured advertisement keys, and publishes the decoded values as native Venus OS D-Bus services. MQTT and InfluxDB outputs are still available, but the main target is now Venus OS: the devices can appear in the Venus GUI and can be forwarded naturally by the Victron stack.

The project vendors the BLE parser logic from [`victron_ble`](https://github.com/keshavdv/victron-ble) and avoids package installs on Venus OS where possible. Advertisement keys are not brute-forced: each key must be retrieved from VictronConnect for a device you own/administer.

## Current Status

Tested on Venus OS 3.73/3.80-class Raspberry Pi installations with Python 3.12 and no `pip` requirement for the Venus D-Bus path.

Supported D-Bus device mappings:

| Device family | `device_type` | Venus service | Main paths |
| --- | --- | --- | --- |
| SmartShunt / battery monitor | `battery` | `com.victronenergy.battery.<id>` | `/Dc/0/Voltage`, `/Dc/0/Current`, `/Dc/0/Power`, `/Soc` |
| Smart Battery Sense | `battery` | `com.victronenergy.battery.<id>` | `/Dc/0/Voltage`, `/Dc/0/Temperature` |
| Orion XS DC-DC charger | `orion_xs` | `com.victronenergy.dcdc.<id>` | `/Dc/0/*`, `/Dc/In/*`, `/State`, `/ErrorCode` |
| SmartSolar / MPPT | `smartsolar` | `com.victronenergy.solarcharger.<id>` | `/Dc/0/*`, `/Yield/Power`, `/History/Daily/0/Yield` |
| SmartCharger / AC charger | `smartcharger` | `com.victronenergy.charger.<id>` | `/Dc/0..2/*`, `/Ac/In/1/Current`, `/Temperature` |

Other Victron Instant Readout payloads may already parse via the vendored `victron_ble` package, but may need a D-Bus mapping before the Venus GUI can use them properly.

## Hardware Target

- Raspberry Pi running Venus OS, tested with Raspberry Pi 3B+
- Raspberry Pi Zero 2 W / 3 / 4 / 5 running regular Linux
- Any Linux host with BlueZ and Bluetooth LE support

BLE range matters. If a device is configured but remains `/Connected = 0`, move the Raspberry Pi closer or improve the antenna/radio placement before debugging the parser.

## Venus OS Quick Start

Copy the project to Venus OS:

```bash
scp -r . root@192.168.1.169:/data/victron-ble-dbus
```

On Venus OS:

```bash
cd /data/victron-ble-dbus
cp examples/config.venus.example.toml config.toml
vi config.toml
PYTHONPATH=src python3 -m victron_ble_mqtt_gateway --config config.toml -v
```

When the manual run works, install the runit service:

```bash
cd /data/victron-ble-dbus
./venus-os/install-service.sh
```

Service control on Venus OS:

```bash
svc -u /service/victron-ble-dbus   # start/up
svc -d /service/victron-ble-dbus   # stop/down
svc -t /service/victron-ble-dbus   # terminate/restart
```

If you launched a manual foreground process and need to stop it:

```bash
pkill -9 -f victron_ble_mqtt_gateway
```

## Configuration

Each device needs:

- `id`: stable local identifier used in D-Bus service names and MQTT topics
- `name`: readable name shown in D-Bus paths such as `/ProductName` and `/CustomName`
- `address`: BLE MAC address
- `advertisement_key`: 32-character hex Instant Readout key from VictronConnect
- `device_type`: D-Bus mapping type; defaults to `battery`

Example:

```toml
[[devices]]
id = "smartshunt"
name = "SmartShunt"
address = "AA:BB:CC:DD:EE:FF"
advertisement_key = "0123456789abcdef0123456789abcdef"
device_type = "battery"
```

Known `device_type` values:

```text
battery       SmartShunt, BMV-like monitors, Smart Battery Sense fallback
orion_xs      Orion XS / DC-DC charger mapping
smartsolar    SmartSolar / MPPT mapping
smartcharger  AC charger mapping
```

Aliases accepted by the code include `dcdc`, `dc_dc`, `solar_charger`, `solarcharger`, `mppt`, `ac_charger`, and `charger`.

## D-Bus Checks

List services:

```bash
dbus -y | grep -i -E 'battery|dcdc|solar|charger'
```

Check representative values:

```bash
dbus -y com.victronenergy.battery.smartshunt /Connected GetValue
dbus -y com.victronenergy.battery.smartshunt /Dc/0/Voltage GetValue

dbus -y com.victronenergy.dcdc.orion_xs /Dc/0/Voltage GetValue
dbus -y com.victronenergy.dcdc.orion_xs /Dc/In/V GetValue

dbus -y com.victronenergy.battery.smart_battery_sense /Dc/0/Temperature GetValue

dbus -y com.victronenergy.solarcharger.smartsolar /Yield/Power GetValue

dbus -y com.victronenergy.charger.smartcharger /Dc/0/Current GetValue
dbus -y com.victronenergy.charger.smartcharger /Temperature GetValue
```

The bridge sets `/Connected` to `0` when no BLE advertisement is seen for `connected_timeout_seconds`.

## Regular Linux / MQTT / InfluxDB

On regular Raspberry Pi OS or another Linux distribution, install the package in a virtual environment:

```bash
sudo apt update
sudo apt install -y python3-venv bluetooth bluez
python3 -m venv .venv
. .venv/bin/activate
pip install .
cp examples/config.example.toml config.toml
victron-ble-mqtt-gateway --config config.toml -v
```

MQTT and InfluxDB outputs are optional. They can be enabled alongside or instead of Venus D-Bus in `config.toml`.

### MQTT

With `base_topic = "victron"` and `id = "smartshunt"`:

```text
victron/gateway/status
victron/smartshunt/status
victron/smartshunt/state
victron/smartshunt/voltage
victron/smartshunt/current
victron/smartshunt/soc
victron/smartshunt/rssi
victron/smartshunt/updated_at
```

### InfluxDB v2

The gateway can write to InfluxDB v2.x, including InfluxDB 2.5.1, using the `/api/v2/write` API.

```toml
[influxdb]
enabled = true
url = "http://192.168.1.12:8086"
token = "paste-your-influxdb-token-here"
org = "home"
bucket = "victron"
measurement = "victron_ble"
```

## Systemd

For non-Venus Linux installs, an example unit is provided:

```bash
sudo cp systemd/victron-ble-mqtt-gateway.service /etc/systemd/system/
sudo cp config.toml /etc/victron-ble-mqtt-gateway.toml
sudo systemctl daemon-reload
sudo systemctl enable --now victron-ble-mqtt-gateway
journalctl -u victron-ble-mqtt-gateway -f
```

## Getting Advertisement Keys

In VictronConnect:

1. Open the device.
2. Open settings.
3. Open Product Info.
4. Enable Instant Readout over Bluetooth.
5. Open/show Instant Readout details.
6. Copy the MAC address and advertisement key.

Keep keys private. Do not commit real keys to GitHub.

## Troubleshooting

### No Bluetooth adapter

If startup fails with `No powered Bluetooth adapters found`, BlueZ does not see an enabled adapter.

```bash
sudo systemctl enable --now bluetooth
rfkill list bluetooth
sudo rfkill unblock bluetooth
bluetoothctl show
```

Inside `bluetoothctl`, if `Powered: no`:

```text
power on
quit
```

On Raspberry Pi, also check that Bluetooth is not disabled in `/boot/firmware/config.txt` or `/boot/config.txt` with an overlay such as `dtoverlay=disable-bt`.

### Device configured but values stay empty

- Confirm the address matches the BLE MAC from Instant Readout details.
- Confirm the `advertisement_key` is exactly 32 hex characters.
- Run with `-v` and look for `Parsed Victron advertisement from ...`.
- Move the Raspberry Pi closer to the Victron devices.
- Check `/Connected`; `0` means no valid advertisement has been seen within the timeout.

### Bus name already exists

A previous foreground run or service instance is still alive:

```bash
svc -d /service/victron-ble-dbus 2>/dev/null
pkill -9 -f victron_ble_mqtt_gateway
```

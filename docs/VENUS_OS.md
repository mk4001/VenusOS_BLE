# Venus OS Deployment

This project can run directly on Venus OS and publish decoded Victron BLE Instant Readout values as local D-Bus services.

## Directory Layout

Recommended install path:

```bash
/data/victron-ble-dbus
```

The runit service scripts in `venus-os/` assume that path.

## Manual Test

```bash
cd /data/victron-ble-dbus
cp examples/config.venus.example.toml config.toml
vi config.toml
PYTHONPATH=src python3 -m victron_ble_mqtt_gateway --config config.toml -v
```

A healthy run logs parsed advertisements and D-Bus updates.

## Service Install

```bash
cd /data/victron-ble-dbus
./venus-os/install-service.sh
svc -u /service/victron-ble-dbus
```

Stop/restart:

```bash
svc -d /service/victron-ble-dbus
svc -t /service/victron-ble-dbus
```

If a foreground test process is still alive and keeps a D-Bus name busy:

```bash
pkill -9 -f victron_ble_mqtt_gateway
```

## D-Bus Service Names

```text
com.victronenergy.battery.<id>
com.victronenergy.dcdc.<id>
com.victronenergy.solarcharger.<id>
com.victronenergy.charger.<id>
```

List active services:

```bash
dbus -y | grep -i -E 'battery|dcdc|solar|charger'
```

## Health Checks

```bash
dbus -y com.victronenergy.battery.smartshunt /Connected GetValue
dbus -y com.victronenergy.dcdc.orion_xs /Connected GetValue
dbus -y com.victronenergy.solarcharger.smartsolar /Connected GetValue
dbus -y com.victronenergy.charger.smartcharger /Connected GetValue
```

`1` means a valid advertisement has been decoded recently. `0` means no advertisement was received within `connected_timeout_seconds`.

## Notes

- Venus OS already includes `dbus`, `gi`, and Victron `vedbus.py`.
- The Venus D-Bus mode does not require MQTT, InfluxDB, `bleak`, or `pip`.
- BLE placement matters. Move the Raspberry Pi closer before assuming a parser/config problem.

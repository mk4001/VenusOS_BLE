# Project Status

## Working

- BlueZ-based BLE scanner for Venus OS without `bleak`.
- Vendored Victron Instant Readout parser/decrypt path.
- Venus OS D-Bus output.
- Optional MQTT output.
- Optional InfluxDB v2 output.
- Dependency-light config parsing for Venus OS environments without `tomllib`/`tomli`.

## Tested Device Classes

- SmartShunt
- Orion XS
- Smart Battery Sense
- SmartSolar / MPPT
- SmartCharger / AC charger

## Next Good Improvements

- Add tests around D-Bus mapping functions using fake services.
- Improve runit logging directory creation on Venus OS.
- Add a `status` helper command that checks all configured `/Connected` paths.
- Consider a project rename if MQTT is no longer the primary output.

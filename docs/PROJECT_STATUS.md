# Project Status

## Working

- BlueZ-based BLE scanner for Venus OS without `bleak`, including fallback behavior when adapter discovery methods are unavailable.
- Vendored Victron Instant Readout parser/decrypt path.
- Venus OS D-Bus output.
- Optional MQTT output.
- Optional InfluxDB v2 output.
- Dependency-light config parsing for Venus OS environments without `tomllib`/`tomli`.
- Venus OS 3.70 runit persistence via `/data/rc.local` boot hook.
- Orion XS unknown `OffReason` fallback to raw integer values.
- AC charger also published as a `dcsource` DC input (`ac_charger`), so gui-v2 shows it as an "AC charger".

## Tested Device Classes

- SmartShunt
- Orion XS
- Smart Battery Sense
- SmartSolar / MPPT
- SmartCharger / AC charger
- SmartCharger as `ac_charger` (charger + `dcsource`/`AcCharger` DC-input view)

## Next Good Improvements

- Add tests around D-Bus mapping functions using fake services.
- Improve runit logging directory creation on Venus OS.
- Add a `status` helper command that checks all configured `/Connected` paths.
- Consider a project rename if MQTT is no longer the primary output.

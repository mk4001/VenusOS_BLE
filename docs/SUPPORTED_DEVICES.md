# Supported Devices

The table below describes the D-Bus mappings currently implemented by `venus_dbus.py`.

| Device | `device_type` | Service prefix | Notes |
| --- | --- | --- | --- |
| SmartShunt / BMV-like battery monitor | `battery` | `com.victronenergy.battery` | Voltage, current, power, SOC. |
| Smart Battery Sense | `battery` | `com.victronenergy.battery` | Voltage and `/Dc/0/Temperature`. |
| Orion XS | `orion_xs` | `com.victronenergy.dcdc` | Output on `/Dc/0/*`, input on `/Dc/In/*`. |
| SmartSolar / MPPT | `smartsolar` | `com.victronenergy.solarcharger` | Battery DC values, solar power, daily yield. |
| SmartCharger / AC charger | `smartcharger` | `com.victronenergy.charger` | Up to three DC outputs, AC input current, charger temperature. |
| SmartCharger as AC-charger DC source | `ac_charger` | `com.victronenergy.charger` **+** `com.victronenergy.dcsource` | As `smartcharger`, plus a second service published as `dcsource` with `/Settings/MonitorMode = -2` (`MonitorMode_DcSource_AcCharger`) so gui-v2 shows it in the DC inputs as an "AC charger". |

Aliases accepted in config:

```text
orion_xs: dcdc, dc_dc
smartsolar: solar_charger, solarcharger, mppt
smartcharger: ac_charger, charger
```

Note that `ac_charger` is not a pure alias of `smartcharger`: it publishes the same
`com.victronenergy.charger` service *and* an extra `com.victronenergy.dcsource`
service. Use `ac_charger` when the charger should be visible in the gui-v2 DC
inputs as an AC charger; use `smartcharger` for the charger-only presentation.

Real advertisement keys must never be committed. Use placeholders in public examples.


## Parser Robustness

Some devices can report values newer than the vendored enum tables. Orion XS `off_reason` is intentionally parsed with a fallback: known values become enum names, unknown values remain raw integers. This prevents a single undocumented value such as `129` from dropping the whole BLE packet.

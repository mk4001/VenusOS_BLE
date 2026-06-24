# Supported Devices

The table below describes the D-Bus mappings currently implemented by `venus_dbus.py`.

| Device | `device_type` | Service prefix | Notes |
| --- | --- | --- | --- |
| SmartShunt / BMV-like battery monitor | `battery` | `com.victronenergy.battery` | Voltage, current, power, SOC. |
| Smart Battery Sense | `battery` | `com.victronenergy.battery` | Voltage and `/Dc/0/Temperature`. |
| Orion XS | `orion_xs` | `com.victronenergy.dcdc` | Output on `/Dc/0/*`, input on `/Dc/In/*`. |
| SmartSolar / MPPT | `smartsolar` | `com.victronenergy.solarcharger` | Battery DC values, solar power, daily yield. |
| SmartCharger / AC charger | `smartcharger` | `com.victronenergy.charger` | Up to three DC outputs, AC input current, charger temperature. |

Aliases accepted in config:

```text
orion_xs: dcdc, dc_dc
smartsolar: solar_charger, solarcharger, mppt
smartcharger: ac_charger, charger
```

Real advertisement keys must never be committed. Use placeholders in public examples.

#!/bin/sh
set -eu
SERVICE_NAME=victron-ble-dbus
PROJECT_DIR=/data/victron-ble-dbus
SERVICE_LINK=/service/$SERVICE_NAME

if [ ! -x "$PROJECT_DIR/venus-os/service/run" ]; then
  echo "Missing executable run script: $PROJECT_DIR/venus-os/service/run" >&2
  exit 1
fi

chmod +x "$PROJECT_DIR/venus-os/service/run"
if [ -f "$PROJECT_DIR/venus-os/service/log/run" ]; then
  mkdir -p /var/log/$SERVICE_NAME
  chmod +x "$PROJECT_DIR/venus-os/service/log/run"
fi
if [ -L "$SERVICE_LINK" ] || [ -e "$SERVICE_LINK" ]; then
  echo "$SERVICE_LINK already exists"
else
  ln -s "$PROJECT_DIR/venus-os/service" "$SERVICE_LINK"
fi

svc -u "$SERVICE_LINK"
echo "Installed $SERVICE_NAME. Logs: tail -f /var/log/$SERVICE_NAME/current"

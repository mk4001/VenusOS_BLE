#!/bin/sh
set -eu

SERVICE_NAME=victron-ble-dbus
PROJECT_DIR=/data/victron-ble-dbus
SERVICE_DIR=$PROJECT_DIR/venus-os/service
SERVICE_LINK=/service/$SERVICE_NAME
RC_LOCAL=/data/rc.local
MARK_BEGIN="# BEGIN $SERVICE_NAME"
MARK_END="# END $SERVICE_NAME"

install_link() {
  if [ -L "$SERVICE_LINK" ] || [ -e "$SERVICE_LINK" ]; then
    echo "$SERVICE_LINK already exists"
  else
    ln -s "$SERVICE_DIR" "$SERVICE_LINK"
  fi
}

install_rc_local() {
  if [ ! -f "$RC_LOCAL" ]; then
    printf '#!/bin/sh

exit 0
' > "$RC_LOCAL"
  fi

  if grep -q "$MARK_BEGIN" "$RC_LOCAL"; then
    echo "$RC_LOCAL already contains $SERVICE_NAME boot hook"
    chmod +x "$RC_LOCAL"
    return
  fi

  tmp="$RC_LOCAL.tmp.$$"
  awk -v begin="$MARK_BEGIN" -v end="$MARK_END" -v service_link="$SERVICE_LINK" -v service_dir="$SERVICE_DIR" -v service_name="$SERVICE_NAME" '
    /^exit 0[[:space:]]*$/ && !inserted {
      print begin
      print "mkdir -p /var/log/" service_name
      print "if [ ! -e "" service_link "" ]; then"
      print "  ln -s "" service_dir "" "" service_link """
      print "fi"
      print "svc -u "" service_link "" 2>/dev/null || true"
      print end
      inserted=1
    }
    { print }
    END {
      if (!inserted) {
        print begin
        print "mkdir -p /var/log/" service_name
        print "if [ ! -e "" service_link "" ]; then"
        print "  ln -s "" service_dir "" "" service_link """
        print "fi"
        print "svc -u "" service_link "" 2>/dev/null || true"
        print end
      }
    }
  ' "$RC_LOCAL" > "$tmp"
  mv "$tmp" "$RC_LOCAL"
  chmod +x "$RC_LOCAL"
  echo "Installed persistent boot hook in $RC_LOCAL"
}

if [ ! -x "$SERVICE_DIR/run" ]; then
  echo "Missing executable run script: $SERVICE_DIR/run" >&2
  exit 1
fi

chmod +x "$SERVICE_DIR/run"
if [ -f "$SERVICE_DIR/log/run" ]; then
  mkdir -p /var/log/$SERVICE_NAME
  chmod +x "$SERVICE_DIR/log/run"
fi

install_link
install_rc_local
svc -u "$SERVICE_LINK"

echo "Installed $SERVICE_NAME. Logs: tail -f /var/log/$SERVICE_NAME/current"

#!/usr/bin/env bash

# Read-only discovery diagnostics for app-capable ULTIMEA soundbars.
# No MAC/model is required. This script does not pair, connect, trust, remove,
# or write to any Bluetooth device.

set -u

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${HOME:-/tmp}/ultimea-discovery-diagnostics-${STAMP}"
REPORT="$OUT/report.txt"
OFF_RAW="$OUT/bar-off-scan.txt"
ON_RAW="$OUT/bar-on-scan.txt"
OFF_ADDR="$OUT/bar-off-addresses.txt"
ON_ADDR="$OUT/bar-on-addresses.txt"
ON_ONLY="$OUT/seen-only-while-bar-on.txt"
ALL_INFO="$OUT/bluez-device-info.txt"
REMOTE_SCANNERS="$OUT/bluetooth-remote-scanners.json"

mkdir -p "$OUT"

say() { printf '%s\n' "$*"; }

section() {
    printf '\n======================================================================\n%s\n======================================================================\n' "$*"
}

have() { command -v "$1" >/dev/null 2>&1; }

extract_addresses() {
    grep -Eo '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' "$1" 2>/dev/null \
        | tr '[:lower:]' '[:upper:]' \
        | sort -u
}

scan_for() {
    local seconds="$1"
    local output="$2"

    : > "$output"

    if ! have bluetoothctl; then
        say "ERROR: bluetoothctl is not installed." | tee -a "$output"
        return 1
    fi

    # Keep one bluetoothctl D-Bus client alive for the entire observation
    # window. `timeout bluetoothctl scan ...` is not reliable with newer
    # bluetoothctl non-interactive behaviour because the command may return
    # immediately after starting discovery.
    {
        printf 'scan le\n'
        sleep "$seconds"
        printf 'scan off\n'
        printf 'quit\n'
    } | bluetoothctl 2>&1 | tee "$output" || true
}

read_enter() {
    local prompt="$1"
    if [ -r /dev/tty ]; then
        printf '%s' "$prompt" > /dev/tty
        IFS= read -r _ < /dev/tty || true
    else
        say "$prompt"
        IFS= read -r _ || true
    fi
}

find_ha_container() {
    have docker || return 0
    docker ps --format '{{.ID}} {{.Names}} {{.Image}}' 2>/dev/null \
        | awk '$2 == "homeassistant" {print $1; exit}'
}

section "ULTIMEA DISCOVERY DIAGNOSTICS — NO MAC / MODEL REQUIRED"
say "Output directory: $OUT"
say
say "Before continuing:"
say "  1. Fully close the ULTIMEA phone app."
say "  2. If possible, temporarily disable Bluetooth on that phone."
say "  3. Do not pair/connect/remove the soundbar from this computer."
say
say "This diagnostic is read-only with respect to Bluetooth devices."

if have bluetoothctl; then
    read_enter "TURN THE SOUNDBAR COMPLETELY OFF, then press ENTER: "
    say
    say "Scanning for 20 seconds with the soundbar OFF..."
    scan_for 20 "$OFF_RAW"
    extract_addresses "$OFF_RAW" > "$OFF_ADDR"

    read_enter "TURN THE SOUNDBAR ON, wait until it has fully booted, then press ENTER: "
    say
    say "Scanning for 40 seconds with the soundbar ON..."
    scan_for 40 "$ON_RAW"
    extract_addresses "$ON_RAW" > "$ON_ADDR"

    comm -13 "$OFF_ADDR" "$ON_ADDR" > "$ON_ONLY" || true
else
    : > "$OFF_RAW"; : > "$ON_RAW"; : > "$OFF_ADDR"; : > "$ON_ADDR"; : > "$ON_ONLY"
fi

: > "$ALL_INFO"
if have bluetoothctl && [ -s "$ON_ADDR" ]; then
    while IFS= read -r mac; do
        [ -n "$mac" ] || continue
        {
            say "----------------------------------------------------------------------"
            say "DEVICE $mac"
            say "----------------------------------------------------------------------"
            bluetoothctl info "$mac" 2>&1 || true
            say
        } >> "$ALL_INFO"
    done < "$ON_ADDR"
fi

ha_container="$(find_ha_container)"
if [ -n "$ha_container" ]; then
    docker exec "$ha_container" sh -c \
        'cat /config/.storage/bluetooth.remote_scanners 2>/dev/null || true' \
        > "$REMOTE_SCANNERS" 2>/dev/null || true
else
    : > "$REMOTE_SCANNERS"
fi

{
    section "HOST"
    date 2>&1 || true
    uname -a 2>&1 || true
    say "SHELL=${SHELL:-unknown}"
    say "USER=${USER:-unknown}"

    section "BLUEZ / LOCAL ADAPTER STATE"
    if have bluetoothctl; then
        bluetoothctl --version 2>&1 || true
        say
        say "--- adapters ---"
        bluetoothctl list 2>&1 || true
        say
        say "--- default adapter ---"
        bluetoothctl show 2>&1 || true
        say
        say "--- cached devices ---"
        bluetoothctl devices 2>&1 || true
    else
        say "bluetoothctl: NOT INSTALLED"
    fi

    say
    say "--- /sys/class/bluetooth ---"
    ls -la /sys/class/bluetooth 2>&1 || true

    section "OFF / ON LOCAL-SCAN COMPARISON"
    say "Addresses with activity while bar OFF:"
    if [ -s "$OFF_ADDR" ]; then cat "$OFF_ADDR"; else say "<NONE>"; fi
    say
    say "Addresses with activity while bar ON:"
    if [ -s "$ON_ADDR" ]; then cat "$ON_ADDR"; else say "<NONE>"; fi
    say
    say "Addresses seen in ON scan but not OFF scan:"
    if [ -s "$ON_ONLY" ]; then cat "$ON_ONLY"; else say "<NONE>"; fi

    section "BLUEZ DETAILS FOR DEVICES OBSERVED WHILE BAR WAS ON"
    if [ -s "$ALL_INFO" ]; then cat "$ALL_INFO"; else say "<NO DEVICE INFO>"; fi

    section "CURRENT HA-ULTIMEA DISCOVERY MATCH ANALYSIS"
    say "Candidate rules:"
    say "  A) manufacturer id 0x0D8C"
    say "  OR"
    say "  B) service UUID 0000260a-0000-1000-8000-00805f9b34fb"
    say "     plus a known ULTIMEA family-name prefix"
    say "  HA discovery requires a connectable path."
    say

    if have bluetoothctl && [ -s "$ON_ADDR" ]; then
        while IFS= read -r mac; do
            [ -n "$mac" ] || continue
            info="$(bluetoothctl info "$mac" 2>&1 || true)"
            name="$(printf '%s\n' "$info" | sed -n 's/^[[:space:]]*Name:[[:space:]]*//p' | head -n1)"
            [ -n "$name" ] || name="$(printf '%s\n' "$info" | sed -n 's/^[[:space:]]*Alias:[[:space:]]*//p' | head -n1)"

            mfr=0; uuid260a=0; family=0; on_only=0
            printf '%s\n' "$info" | grep -Eqi 'ManufacturerData.Key:[[:space:]]*0x0*[dD]8[cC]([^0-9A-Fa-f]|$)' && mfr=1
            printf '%s\n' "$info" | grep -Eqi '0000260a-0000-1000-8000-00805f9b34fb' && uuid260a=1
            printf '%s\n' "$name" | grep -Eqi '^(poseidon|apollo|nova|aura|solo|skywave)' && family=1
            grep -Fqx "$mac" "$ON_ONLY" 2>/dev/null && on_only=1

            say "DEVICE $mac"
            say "  name=${name:-<NONE>}"
            say "  appeared_only_in_on_scan=$on_only"
            say "  manufacturer_0x0D8C=$mfr"
            say "  discovery_uuid_260A=$uuid260a"
            say "  known_family_prefix=$family"
            if [ "$mfr" -eq 1 ]; then
                say "  current_integration_match=YES_MANUFACTURER"
            elif [ "$uuid260a" -eq 1 ] && [ "$family" -eq 1 ]; then
                say "  current_integration_match=YES_UUID_AND_NAME"
            else
                say "  current_integration_match=NO"
            fi
            say
        done < "$ON_ADDR"
    else
        say "No local ON-scan device addresses were captured."
    fi

    section "HOME ASSISTANT ENVIRONMENT"
    if have ha; then
        say "INSTALLATION=HA_OS_OR_SUPERVISED"
        say
        say "--- HA core info ---"
        ha core info 2>&1 || true
        say
        say "--- recent HA Bluetooth / ULTIMEA logs ---"
        ha core logs 2>&1 \
            | grep -Ei 'ultimea|bluetooth|bleak|bluez|dbus|hci|0d8c|260a|8daa|8d11|8d22|8d55|8d66|discovery|connectable|cannot_connect|not_supported' \
            | tail -n 500 || true
    elif [ -n "$ha_container" ]; then
        say "INSTALLATION=HOME_ASSISTANT_CONTAINER"
    else
        say "Home Assistant installation type could not be identified from this shell."
    fi

    if [ -n "$ha_container" ]; then
        say
        say "--- Home Assistant core container ---"
        docker inspect "$ha_container" \
            --format 'Name={{.Name}} Image={{.Config.Image}} NetworkMode={{.HostConfig.NetworkMode}} Privileged={{.HostConfig.Privileged}}' \
            2>&1 || true
        say
        say "--- installed ULTIMEA manifest ---"
        docker exec "$ha_container" sh -c \
            'if [ -f /config/custom_components/ultimea/manifest.json ]; then cat /config/custom_components/ultimea/manifest.json; else echo "<NOT INSTALLED>"; fi' \
            2>&1 || true
        say
        say "--- existing ULTIMEA config-entry fragments ---"
        docker exec "$ha_container" sh -c \
            'if [ -f /config/.storage/core.config_entries ]; then grep -n -i -C 3 "ultimea" /config/.storage/core.config_entries || true; else echo "<core.config_entries unavailable>"; fi' \
            2>&1 || true
    fi

    section "HOME ASSISTANT REMOTE BLUETOOTH SCANNERS"
    if [ -s "$REMOTE_SCANNERS" ]; then
        say "--- connectable flags ---"
        grep -En -B 2 -A 1 '"connectable"[[:space:]]*:[[:space:]]*(true|false)' "$REMOTE_SCANNERS" || true
        say
        say "--- ULTIMEA-like advertisements in HA remote-scanner storage ---"
        grep -Ein -B 8 -A 16 \
            '3468|0d8c|poseidon|apollo|nova|ultimea|0000260a-0000-1000-8000-00805f9b34fb' \
            "$REMOTE_SCANNERS" || true
    else
        say "<REMOTE SCANNER STORAGE NOT AVAILABLE FROM THIS SHELL>"
    fi

    section "RAW BAR-OFF LOCAL SCAN"
    cat "$OFF_RAW" 2>/dev/null || true

    section "RAW BAR-ON LOCAL SCAN"
    cat "$ON_RAW" 2>/dev/null || true

    section "INTERPRETATION GUIDE"
    say "1. A local ON-only ULTIMEA advertisement with 0x0D8C should match discovery."
    say "2. A D80 seen only by remote scanners marked connectable=false cannot be used for GATT."
    say "3. If a connectable local/proxy scanner sees the D80 but HA-ULTIMEA does not offer it, inspect config-flow/discovery handling."
    say "4. If only non-connectable scanners see it, the remaining issue is Bluetooth connection-path coverage."

} > "$REPORT" 2>&1

section "DONE"
say "Send this file:"
say "  $REPORT"
say
say "Also send this file if it is non-empty:"
say "  $REMOTE_SCANNERS"
say
say "No MAC/model was required and no Bluetooth connection/write was attempted."

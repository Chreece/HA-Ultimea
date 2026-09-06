#!/usr/bin/env bash

# Read-only discovery diagnostics for app-capable ULTIMEA soundbars.
#
# This script does NOT require a MAC address or model name and does NOT pair,
# connect, remove, trust, or write to any Bluetooth device. It compares BLE
# scan activity with the soundbar powered off/on and records why the current
# HA-ULTIMEA discovery matcher would accept or ignore each observed device.

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

mkdir -p "$OUT"

say() {
    printf '%s\n' "$*"
}

section() {
    printf '\n======================================================================\n%s\n======================================================================\n' "$*"
}

have() {
    command -v "$1" >/dev/null 2>&1
}

extract_addresses() {
    local source="$1"
    grep -Eo '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' "$source" 2>/dev/null \
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

    # timeout terminates bluetoothctl itself. No global adapter reset, pairing,
    # connection or device mutation is performed.
    if have timeout; then
        timeout "${seconds}s" bluetoothctl scan on 2>&1 | tee "$output" || true
    else
        # bluetoothctl itself supports --timeout on modern BlueZ builds.
        bluetoothctl --timeout "$seconds" scan on 2>&1 | tee "$output" || true
    fi

    bluetoothctl scan off >/dev/null 2>&1 || true
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

section "ULTIMEA DISCOVERY DIAGNOSTICS — NO MAC / MODEL REQUIRED"
say "Output directory: $OUT"
say
say "Before continuing:"
say "  1. Fully close the ULTIMEA phone app."
say "  2. If possible, temporarily disable Bluetooth on that phone."
say "  3. Do not pair/connect/remove the soundbar from this computer."
say
say "This diagnostic is read-only with respect to Bluetooth devices."

if ! have bluetoothctl; then
    say
    say "ERROR: bluetoothctl is required. The report will still contain basic host information."
else
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
fi

# Capture details outside the main report first so the report can remain a
# single shareable file even if some bluetoothctl calls are slow or noisy.
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

{
    section "HOST"
    date 2>&1 || true
    uname -a 2>&1 || true
    say "SHELL=${SHELL:-unknown}"
    say "USER=${USER:-unknown}"

    section "BLUEZ / ADAPTER STATE"
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
    say "--- rfkill ---"
    if have rfkill; then
        rfkill list bluetooth 2>&1 || true
    else
        say "rfkill: not installed"
    fi

    say
    say "--- /sys/class/bluetooth ---"
    ls -la /sys/class/bluetooth 2>&1 || true

    section "OFF / ON SCAN COMPARISON"
    say "Addresses with activity while bar OFF:"
    if [ -s "$OFF_ADDR" ]; then cat "$OFF_ADDR"; else say "<NONE>"; fi
    say
    say "Addresses with activity while bar ON:"
    if [ -s "$ON_ADDR" ]; then cat "$ON_ADDR"; else say "<NONE>"; fi
    say
    say "Addresses seen in ON scan but not OFF scan:"
    if [ -s "$ON_ONLY" ]; then cat "$ON_ONLY"; else say "<NONE>"; fi

    section "BLUEZ DETAILS FOR DEVICES OBSERVED WHILE BAR WAS ON"
    if [ -s "$ALL_INFO" ]; then
        cat "$ALL_INFO"
    else
        say "<NO DEVICE INFO>"
    fi

    section "CURRENT HA-ULTIMEA DISCOVERY MATCH ANALYSIS"
    say "Current integration candidate rules:"
    say "  A) manufacturer id 0x0D8C"
    say "  OR"
    say "  B) service UUID 0000260a-0000-1000-8000-00805f9b34fb"
    say "     plus a known ULTIMEA family-name prefix"
    say "  Home Assistant discovery also requests connectable advertisements."
    say

    if have bluetoothctl && [ -s "$ON_ADDR" ]; then
        while IFS= read -r mac; do
            [ -n "$mac" ] || continue
            info="$(bluetoothctl info "$mac" 2>&1 || true)"

            name="$(printf '%s\n' "$info" | sed -n 's/^[[:space:]]*Name:[[:space:]]*//p' | head -n1)"
            if [ -z "$name" ]; then
                name="$(printf '%s\n' "$info" | sed -n 's/^[[:space:]]*Alias:[[:space:]]*//p' | head -n1)"
            fi

            mfr=0
            uuid260a=0
            family=0
            ultima_name=0
            on_only=0

            printf '%s\n' "$info" | grep -Eqi 'ManufacturerData.Key:[[:space:]]*0x0*[dD]8[cC]([^0-9A-Fa-f]|$)' && mfr=1
            printf '%s\n' "$info" | grep -Eqi '0000260a-0000-1000-8000-00805f9b34fb' && uuid260a=1
            printf '%s\n' "$name" | grep -Eqi '^(poseidon|apollo|nova|aura|solo|skywave)' && family=1
            printf '%s\n' "$name" | grep -Eqi 'ultimea' && ultima_name=1
            grep -Fqx "$mac" "$ON_ONLY" 2>/dev/null && on_only=1

            score=0
            [ "$mfr" -eq 1 ] && score=$((score + 100))
            [ "$uuid260a" -eq 1 ] && score=$((score + 50))
            [ "$family" -eq 1 ] && score=$((score + 30))
            [ "$ultima_name" -eq 1 ] && score=$((score + 30))
            [ "$on_only" -eq 1 ] && score=$((score + 20))

            say "DEVICE $mac"
            say "  name=${name:-<NONE>}"
            say "  appeared_only_in_on_scan=$on_only"
            say "  manufacturer_0x0D8C=$mfr"
            say "  discovery_uuid_260A=$uuid260a"
            say "  known_family_prefix=$family"
            say "  name_contains_ultimea=$ultima_name"
            say "  diagnostic_candidate_score=$score"

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
        say "No ON-scan device addresses were available for matcher analysis."
    fi

    section "BLUEZ JOURNAL"
    if have journalctl; then
        journalctl -u bluetooth --since '-30 min' --no-pager 2>&1 | tail -n 300 || true
    else
        say "journalctl: not installed"
    fi

    section "KERNEL BLUETOOTH MESSAGES"
    if have dmesg; then
        dmesg --ctime 2>&1 | grep -Ei 'bluetooth|bluez|btusb|hci[0-9]' | tail -n 250 || true
    else
        say "dmesg: not available"
    fi

    section "HOME ASSISTANT ENVIRONMENT"

    ha_found=0

    if have docker; then
        ha_container="$(docker ps --format '{{.ID}} {{.Names}} {{.Image}}' 2>/dev/null \
            | awk 'tolower($0) ~ /homeassistant|home-assistant\/home-assistant/ {print $1; exit}')"

        if [ -n "$ha_container" ]; then
            ha_found=1
            say "INSTALLATION=HOME_ASSISTANT_CONTAINER"
            say "CONTAINER_ID=$ha_container"
            say
            docker inspect "$ha_container" --format 'Name={{.Name}} Image={{.Config.Image}} NetworkMode={{.HostConfig.NetworkMode}} Privileged={{.HostConfig.Privileged}}' 2>&1 || true
            say
            say "--- mounts ---"
            docker inspect "$ha_container" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}' 2>&1 || true
            say
            say "--- host DBus ---"
            ls -l /run/dbus/system_bus_socket 2>&1 || true
            say
            say "--- DBus visible inside HA ---"
            docker exec "$ha_container" sh -c 'ls -l /run/dbus/system_bus_socket 2>&1 || true' 2>&1 || true
            say
            say "--- installed ULTIMEA manifest ---"
            docker exec "$ha_container" sh -c 'if [ -f /config/custom_components/ultimea/manifest.json ]; then cat /config/custom_components/ultimea/manifest.json; else echo "<NOT INSTALLED>"; fi' 2>&1 || true
            say
            say "--- existing ULTIMEA config-entry fragments ---"
            docker exec "$ha_container" sh -c 'if [ -f /config/.storage/core.config_entries ]; then grep -n -i -C 3 "ultimea" /config/.storage/core.config_entries || true; else echo "<core.config_entries unavailable>"; fi' 2>&1 || true
            say
            say "--- recent HA Bluetooth / ULTIMEA logs ---"
            docker logs --since 30m "$ha_container" 2>&1 \
                | grep -Ei 'ultimea|bluetooth|bleak|bluez|dbus|hci|0d8c|260a|8daa|8d11|8d22|8d55|8d66|discovery|connectable|cannot_connect|not_supported' \
                | tail -n 500 || true
        fi
    fi

    if have ha; then
        ha_found=1
        say
        say "INSTALLATION=HA_OS_OR_SUPERVISED_CLI_PRESENT"
        say
        say "--- HA core info ---"
        ha core info 2>&1 || true
        say
        say "--- HA hardware ---"
        ha hardware info 2>&1 || true
        say
        say "--- recent HA Bluetooth / ULTIMEA logs ---"
        ha core logs 2>&1 \
            | grep -Ei 'ultimea|bluetooth|bleak|bluez|dbus|hci|0d8c|260a|8daa|8d11|8d22|8d55|8d66|discovery|connectable|cannot_connect|not_supported' \
            | tail -n 500 || true
    fi

    if [ "$ha_found" -eq 0 ]; then
        say "Could not automatically identify a Home Assistant Container or HA CLI installation from this shell."
    fi

    section "RAW BAR-OFF SCAN"
    if [ -f "$OFF_RAW" ]; then cat "$OFF_RAW"; else say "<NOT CAPTURED>"; fi

    section "RAW BAR-ON SCAN"
    if [ -f "$ON_RAW" ]; then cat "$ON_RAW"; else say "<NOT CAPTURED>"; fi

    section "INTERPRETATION GUIDE"
    say "1. A high-scoring device that appears only with the bar ON is the primary candidate."
    say "2. current_integration_match=NO on that candidate means the manifest/config-flow matcher is too narrow for that model's advertisement."
    say "3. current_integration_match=YES but no HA discovery points to HA Bluetooth routing/connectable-cache/config-flow handling."
    say "4. No plausible ON-only candidate on a host with a local adapter points below the integration (radio visibility/advertising)."
    say "5. If the installation relies only on ESPHome Bluetooth proxies, host bluetoothctl may see nothing; the HA log section is then the relevant evidence."

} > "$REPORT" 2>&1

section "DONE"
say "Send this file:"
say "  $REPORT"
say
say "Raw ON scan (only if requested):"
say "  $ON_RAW"
say
say "No MAC/model was required and no Bluetooth connection/write was attempted."

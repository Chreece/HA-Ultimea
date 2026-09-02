#!/usr/bin/env bash
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M%S)"
MARKERS="$HOME/d80-audio-markers-$STAMP.txt"
BUGREPORT="$HOME/d80-audio-bugreport-$STAMP.zip"

mark() {
    local label="$1"
    printf '%s\t%s\n' "$(date '+%s.%N')" "$label" | tee -a "$MARKERS"
    adb shell log -p i -t D80AUDIO "$label" >/dev/null 2>&1 || true
}

prepare() {
    local text="$1"
    echo
    echo "PREPARE (not the target action): $text"
    read -r -p "Do that now, then press ENTER: "
    sleep 1
}

target() {
    local label="$1"
    local text="$2"
    echo
    echo "============================================================"
    echo " $label"
    echo "============================================================"
    echo "$text"
    read -r -p "Press ENTER when you are ready to perform it: "
    mark "BEGIN $label"
    read -r -p "Perform it ONCE now, then press ENTER: "
    sleep 1
    mark "END $label"
}

command -v adb >/dev/null || { echo "adb not found"; exit 1; }
adb get-state >/dev/null || { echo "No ADB device connected"; exit 1; }

echo "Poseidon D80 Boom — targeted advanced-audio HCI capture"
echo
echo "Current Bluetooth snoop state reported by Samsung:"
adb shell dumpsys bluetooth_manager 2>/dev/null | grep -E 'sSnoopLogSettingAtEnable|sDefaultSnoopLogSettingAtEnable' || true

echo
echo "Keep the ULTIMEA app connected to the D80."
echo "Use the APP for every target action below, not the physical remote."
echo "Preparation changes are intentionally outside the target markers."
read -r -p "Press ENTER when the app is connected and ready: "

mark "CAPTURE START"

prepare "Navigate AWAY from the Customize Sound / tone-control page."
target "OPEN CUSTOM SOUND PAGE" "Open the app page that exposes Bass / Mid / Treble. Do not change a value yet."

prepare "In Customize Sound, put BASS at 0 (or the displayed neutral value)."
target "BASS PLUS ONE" "Change Bass exactly one step upward: 0 -> +1."
prepare "Put BASS back at 0."
target "BASS MINUS ONE" "Change Bass exactly one step downward: 0 -> -1."

prepare "Put MID / MIDDLE at 0."
target "MID PLUS ONE" "Change Mid/Middle exactly one step upward: 0 -> +1."
prepare "Put MID / MIDDLE back at 0."
target "MID MINUS ONE" "Change Mid/Middle exactly one step downward: 0 -> -1."

prepare "Put TREBLE at 0."
target "TREBLE PLUS ONE" "Change Treble exactly one step upward: 0 -> +1."
prepare "Put TREBLE back at 0."
target "TREBLE MINUS ONE" "Change Treble exactly one step downward: 0 -> -1."

prepare "Open the app's Surround level control and set it to 3 (or another middle value if 3 is unavailable)."
target "SURROUND PLUS ONE" "Increase Surround exactly one step (preferably 3 -> 4)."
prepare "Return Surround to the same middle baseline used above."
target "SURROUND MINUS ONE" "Decrease Surround exactly one step (preferably 3 -> 2)."

prepare "Set X-Upmix/Xupmix to OFF in the app."
target "XUPMIX ON" "Turn X-Upmix ON exactly once."
prepare "Make sure X-Upmix is ON."
target "XUPMIX OFF" "Turn X-Upmix OFF exactly once."

echo
echo "OPTIONAL: if the app exposes other advanced audio controls (10-band EQ, style, etc.),"
echo "you can capture them now. Leave the label blank to finish."
while true; do
    read -r -p "Extra control label (blank = finish): " label
    [[ -z "$label" ]] && break
    target "EXTRA $label" "Prepare the value first if needed, then change ONLY the requested control once."
done

mark "CAPTURE END"

echo
echo "Generating Samsung bugreport with the Bluetooth HCI snoop..."
adb bugreport "$BUGREPORT"

echo
echo "DONE"
echo "Upload both files:"
echo "  $BUGREPORT"
echo "  $MARKERS"

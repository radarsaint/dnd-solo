#!/usr/bin/env bash
# Install Kit's table host inside Termux on the tablet. Not a root install.
# Run from Termux:  bash install.sh
# This does not install a voice model. The rules engine and the voice are separate.
set -euo pipefail

if ! command -v pkg >/dev/null 2>&1 || [[ ! -d /data/data/com.termux ]]; then
  echo "This installer is for Termux on the Android tablet. It did not run."
  exit 1
fi

pkg update -y
pkg install -y python git termux-api curl

REPO="${KIT_REPO:-$HOME/dnd-solo}"
if [[ ! -d "$REPO/.git" ]]; then
  git clone --depth 1 https://github.com/radarsaint/dnd-solo.git "$REPO"
fi
cd "$REPO"
git pull --ff-only || true

python3 - << 'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit('Kit needs Python 3.10 or newer. Termux python is too old.')
print('python', sys.version.split()[0])
PY

python3 -m compileall -q runtime host
mkdir -p "$HOME/.kit-table" "$HOME/.shortcuts"
install -m 700 host/android/launch.sh "$HOME/.shortcuts/Kit"

echo
echo "Kit's rules engine is installed under $REPO"
echo "Home-screen launcher: Termux:Widget shortcut named Kit"
echo "Voice is not installed. Open Kit, then read host/android/README.md before connecting one."
echo "This script did not flash an APK and did not check a physical display."

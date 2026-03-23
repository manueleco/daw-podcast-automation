#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SOURCE="$SCRIPT_DIR/macos/Logic Podcast Automation.js"
APP_TARGET="$SCRIPT_DIR/Logic Podcast Automation.app"

/usr/bin/osacompile -l JavaScript -o "$APP_TARGET" "$APP_SOURCE"

echo "App generada en: $APP_TARGET"

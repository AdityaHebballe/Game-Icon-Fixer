#!/bin/bash
set -e

echo "Uninstalling Game Icon Fixer..."

# Define directories
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

# Remove the executable
if [ -f "$BIN_DIR/game-icon-fixer" ]; then
    echo "Removing executable from $BIN_DIR..."
    rm "$BIN_DIR/game-icon-fixer"
fi

# Remove the desktop entry
if [ -f "$APP_DIR/com.github.adityahebballe.GameIconFixer.desktop" ]; then
    echo "Removing desktop entry from $APP_DIR..."
    rm "$APP_DIR/com.github.adityahebballe.GameIconFixer.desktop"
fi

# Remove the icon
if [ -f "$ICON_DIR/com.github.adityahebballe.GameIconFixer.svg" ]; then
    echo "Removing icon from $ICON_DIR..."
    rm "$ICON_DIR/com.github.adityahebballe.GameIconFixer.svg"
fi

echo "Refreshing desktop databases..."
update-desktop-database "$APP_DIR" || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true

echo "--------------------------------------------------------"
echo "✅ Uninstallation complete!"

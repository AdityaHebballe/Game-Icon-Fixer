#!/bin/bash
set -e

echo "Installing Game Icon Fixer..."

# Define user-local directories per XDG spec
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

# Ensure directories exist
mkdir -p "$BIN_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"

echo "Installing executable..."
# Make sure main.py is executable and copy it to a generically named bin binary
install -m 755 main.py "$BIN_DIR/game-icon-fixer"

echo "Installing desktop entry..."
install -m 644 com.github.adityahebballe.GameIconFixer.desktop "$APP_DIR/"

echo "Installing icon..."
install -m 644 com.github.adityahebballe.GameIconFixer.svg "$ICON_DIR/"

echo "Refreshing desktop databases..."
update-desktop-database "$APP_DIR" || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true

echo "--------------------------------------------------------"
echo "✅ Installation complete!"
echo "You can now launch 'Game Icon Fixer' from your application menu."
echo "Note: Make sure $BIN_DIR is added to your system \$PATH if it isn't already."

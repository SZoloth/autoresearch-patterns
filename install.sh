#!/usr/bin/env bash
set -euo pipefail

# Install autoresearch — clone repo + symlink to PATH.
# Usage: curl -sL <url>/install.sh | bash

INSTALL_DIR="${AUTORESEARCH_HOME:-$HOME/.autoresearch}"
BIN_DIR="/usr/local/bin"
REPO_URL="https://github.com/samzoloth/autoresearch-patterns.git"

echo "Installing autoresearch to $INSTALL_DIR..."

# Check for git
if ! command -v git &>/dev/null; then
    echo "Error: git is required but not found." >&2
    exit 1
fi

# Check for python3
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found." >&2
    exit 1
fi

# Clone or update
if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "Existing installation found. Updating..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    if [[ -d "$INSTALL_DIR" ]]; then
        echo "Error: $INSTALL_DIR exists but is not a git repo. Remove it first." >&2
        exit 1
    fi
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Make scripts executable
chmod +x "$INSTALL_DIR/bin/autoresearch"
chmod +x "$INSTALL_DIR/init.sh"

# Symlink to PATH
if [[ -w "$BIN_DIR" ]]; then
    ln -sf "$INSTALL_DIR/bin/autoresearch" "$BIN_DIR/autoresearch"
else
    echo "Need permission to write to $BIN_DIR..."
    sudo ln -sf "$INSTALL_DIR/bin/autoresearch" "$BIN_DIR/autoresearch"
fi

echo ""
echo "Installed. Run 'autoresearch help' to get started."

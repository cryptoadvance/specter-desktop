#!/bin/bash

# Exit on any error
set -e

# Check if jq is installed (required for JSON manipulation)
if ! command -v jq &> /dev/null; then
    echo "jq could not be found. Please install jq to run this script."
    exit 1
fi

# Check that a version has been supplied
if [ -z "$1" ]; then
  echo "Usage: $0 <version-tag>"
  exit 1
fi

VERSION="$1"
DOWNLOAD_URL="https://github.com/cryptoadvance/specter-desktop/releases/download/${VERSION}/specterd-${VERSION}-osx.zip"
DOWNLOAD_PATH="/tmp/specterd-${VERSION}.zip"
EXTRACT_DIR="/tmp/specterd_extracted"
APP_SETTINGS_FILE="$HOME/.specter_dev/app_settings.json"

# Download the specified version only if it's not already downloaded
echo "Checking if specterd version $VERSION is already downloaded..."
if [ ! -f "$DOWNLOAD_PATH" ]; then
    echo "Downloading specterd version $VERSION from $DOWNLOAD_URL..."
    curl -o "$DOWNLOAD_PATH" -L "$DOWNLOAD_URL"
else
    echo "Using previously downloaded file: $DOWNLOAD_PATH"
fi

# Verify that the downloaded file is a ZIP file
if ! file "$DOWNLOAD_PATH" | grep -q 'Zip archive data'; then
    echo "Downloaded file is not a valid ZIP archive. Exiting..."
    exit 1
fi

# Create a temporary directory for extraction
mkdir -p "$EXTRACT_DIR"
# Unzip the file
echo "Unpacking specterd..."
unzip -o "$DOWNLOAD_PATH" -d "$EXTRACT_DIR"

# Assuming that the name of the binary inside the zip is 'specterd'
SPECTERD_BIN="${EXTRACT_DIR}/specterd"

# Calculate the sha256 sum
echo "Calculating SHA256 sum..."
SPECTERD_HASH=$(sha256sum "$SPECTERD_BIN" | awk '{print $1}')

# Update the app_settings.json with the new hash and version
echo "Updating $APP_SETTINGS_FILE with the new hash and version..."
jq --arg hash "$SPECTERD_HASH" --arg version "$VERSION" \
   '.specterdHash = $hash | .specterdVersion = $version' \
   "$APP_SETTINGS_FILE" > "$APP_SETTINGS_FILE.tmp"

# Replace the original json file with the updated one
mv "$APP_SETTINGS_FILE.tmp" "$APP_SETTINGS_FILE"

# Clean up
echo "Cleaning up..."
rm -rf "$EXTRACT_DIR"

echo "Updated to specterd $VERSION with SHA256 hash $SPECTERD_HASH"

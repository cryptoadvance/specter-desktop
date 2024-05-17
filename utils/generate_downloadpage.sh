#!/usr/bin/env bash
set -e

# We start in the directory where this script is located
cd "$(dirname "${BASH_SOURCE[0]}")/."
source ../.env/bin/activate
cd .. && pip3 install -e ".[gendownloadpage]" && cd utils
rm -rf build
mkdir -p build
python3 ./generate_downloadpage.py

# Update Github Release Page
latest_release=$(python3 -c 'import json; import requests; ver = json.loads(requests.get("https://api.github.com/repos/cryptoadvance/specter-desktop/releases/latest", headers={"Accept": "application/vnd.github.v3+json"}).text)["name"]; print(ver)')

if ! command -v gh &> /dev/null; then
    echo "WARNING: 'gh' binary not found or not executable. Please ensure it is installed and in your PATH."
    echo "You need now to manually replace the release-Notes. I'll list them here:"
    echo "------(snip)-->-8---(snap)--8-<-------------"
    cat build/gh_page.md
    echo "------(snip)-->-8---(snap)--8-<-------------"
    read -p "Press a button to continue when you've done it ..."
else
    read -p "Update the Github Release page for version $latest_release ? (y/n): " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        gh release edit $latest_release --repo cryptoadvance/specter-desktop --notes-file build/gh_page.md
    fi
fi


if ! [[ -d ../../specter-static ]]; then
  echo "You don't have cloned the specter-static repo."
  echo "Go and clone it and then run this script again!"
  exit 1
fi

cp build/download-page.html ../../specter-static/specter-httrack-src/specter.solutions/downloads/index.html

# Change to the Git working directory
cd ../../specter-static

# Check if working directory is clean
if git diff --quiet && git diff --staged --quiet; then
  echo "Git working directory is clean. Exiting..."
  exit 0
fi

# Add the file to the staging area
git add specter-httrack-src/specter.solutions/downloads/index.html

# Commit the changes
read -p "Commit changes? (y/n): " confirm
if [[ $confirm =~ ^[Yy]$ ]]; then
    git commit -m "Update specter.solutions/downloads/index.html"
else
    echo "Commit aborted."
    exit 1
fi

# Push the commit
read -p "Push commit to remote? (y/n): " confirm
if [[ $confirm =~ ^[Yy]$ ]]; then
    git push
else
    echo "Push aborted."
    exit 1
fi

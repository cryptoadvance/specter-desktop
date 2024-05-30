#!/usr/bin/env bash
set -e

# We start in the directory where this script is located
cd "$(dirname "${BASH_SOURCE[0]}")/."

# Function to install GitHub CLI on macOS
install_gh_macos() {
  if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  echo "Installing GitHub CLI using Homebrew..."
  brew install gh
}

# Function to install GitHub CLI on Linux
install_gh_linux() {
  echo "Installing GitHub CLI using official script..."
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  apt update
  apt install gh
}

function prereq {
  if [[ ! -f ../.env/bin/activate ]]; then
    pip3 install --upgrade virtualenv
    virtualenv --python=python3.10 ../.env
  fi
  source ../.env/bin/activate
    # Check if the 'markdown' package is installed in the Python environment
    # 'set -e' does not cause the script to exit if a command in an 'if' statement fails
  if ! python3 -c "import markdown" &> /dev/null; then
      echo " --> The 'markdown' package is not installed. Installing prerequisites..."
      # Change to parent directory, perform installation, and change back
      pushd .. 
      pip3 install -e ".[gendownloadpage]" 
      popd
  else
      echo " --> The 'markdown' package is already installed."
  fi


}

function clean {
    rm -rf build
    mkdir -p build
}

check_version_exists() {
  org_name="$1"
  version="$2"

  # Fetch all tags from the GitHub repository
  tags_response=$(curl -s "https://api.github.com/repos/${org_name}/specter-desktop/tags" \
                  -H "Accept: application/vnd.github.v3+json")

  # Check the response for the specific version
  if ! echo "$tags_response" | jq -e --arg version "$version" '.[] | select(.name == $version)' > /dev/null; then
    echo "ERROR: The version $version does not exist in the org $org_name."
    exit 1
  fi
}

function generate {
  mkdir -p build
  python3 ./generate_downloadpage.py
}

function update_github {
    # Determine the platform and execute the appropriate function
    platform="$(uname -s)"
    case "${platform}" in
      Linux*)     install_gh_linux;;
      Darwin*)    install_gh_macos;;
      *)          echo "Unsupported platform: ${platform}"; exit 1;;
    esac
    if ! command -v gh &> /dev/null; then
        echo "WARNING: 'gh' binary not found or not executable. Please ensure it is installed and in your PATH."
        echo "You need now to manually replace the release-Notes. I'll list them here:"
        echo "------(snip)-->-8---(snap)--8-<-------------"
        cat build/gh_page.md
        echo "------(snip)-->-8---(snap)--8-<-------------"
        read -p "Press a button to continue when you've done it ..."
    else
        gh release edit $version --repo ${org_name}/specter-desktop --notes-file build/gh_page.md
    fi
}

function update_webpage {
    if [[ $version =~ -pre[0-9]+$ ]]; then
      if [[ "$static_repo_org_name" = "swan-bitcoin" ]]; then
        echo "The version has a pre-release suffix. Exiting..."
        return 0
      fi
      echo "we have a pre-release but continuing for testing purposes anyway"
    fi
    if ! [[ -d ../../specter-static ]]; then
      echo "You don't have cloned the specter-static repo."
      echo "doing that now"
      git clone git@github.com:${static_repo_org_name}/specter-static.git
      specter_static_folder=./specter-static
    else
      specter_static_folder=../../specter-static
    fi
    target_file=${specter_static_folder}/specter-httrack-src/specter.solutions/downloads/index.html

    cp build/download-page.html $target_file

    # Change to the Git working directory
    cd $specter_static_folder

    # Check if working directory is clean
    if git diff --quiet && git diff --staged --quiet; then
      echo "Git working directory is clean. Exiting..."
      exit 0
    fi

    # Add the file to the staging area
    git add specter-httrack-src/specter.solutions/downloads/index.html

    # Commit the changes
    git commit -m "Update specter.solutions/downloads/index.html"

    # Push the commit
    #read -p "Push commit to remote? (y/n): " confirm
    #if [[ $confirm =~ ^[Yy]$ ]]; then
    git push
    #else
    #    echo "Push aborted."
    #    exit 1
    #fi
}

function sub_help {
    cat << EOF

# Example-call:
./utils/generate_downloadpage.sh --debug --version v1.10.0-pre23 generate
EOF
}

while [[ $# -gt 0 ]]
  do
  arg="$1"
  case $arg in
      "" | "-h" | "--help")
        sub_help
        exit 0
        shift
        ;;
      --debug)
        set -x
        DEBUG=true
        shift
        ;;
      --version)
        version=$2
        shift
        shift
        ;;
      --org_name)
        org_name=$2
        shift
        shift
        ;;
      generate)
        generate=True
        shift
        ;;
      github)
        change_github=True
        shift
        ;;
      webpage)
        change_webpage=True
        shift
        ;;        
      help)
        sub_help
        shift
        ;;
      *)
          shift
          sub_${arg} $@ && ret=0 || ret=$?
          if [ "$ret" = 127 ]; then
              echo "Error: '$arg' is not a known subcommand." >&2
              echo "       Run '$progname --help' for a list of known subcommands." >&2
              exit 1
          else
              exit $ret_value
          fi
          ;;
  esac
done

if [[ "$org_name" = "cryptoadvance" ]]; then
  static_repo_org_name=swan-bitcoin # that's where the original specter-static is hosted
else
  static_repo_org_name=$org_name # test-repos are assumed to be hosted in the same org than the specter-desktop repo
fi

if [[ -z "$version" ]]; then
    version=$(python3 << EOF
import json
import requests

org_name = "${org_name}"
url = f"https://api.github.com/repos/{org_name}/specter-desktop/releases/latest"
headers = {"Accept": "application/vnd.github.v3+json"}
response = requests.get(url, headers=headers)
release_info = json.loads(response.text)
print(release_info['name'])
EOF
)
fi
check_version_exists "$org_name" "$version"
echo "    --> using version $version"

prereq

if [[ "$generate" = "True" ]]; then
  
  generate
fi

if [[ "$change_github" = "True" ]]; then
  # Check if 'gh' is already installed
  if command -v gh &> /dev/null; then
      echo "GitHub CLI is already installed."
  else
      echo "GitHub CLI is not installed."

      # Detect the platform (Linux or Darwin/macOS)
      platform=$(uname -s)

      case "$platform" in
      Linux) install_gh_linux ;;
      Darwin) install_gh_macos ;;
      *)
          echo "Unsupported platform: $platform"
          exit 1
          ;;
      esac
  fi
  export GH_TOKEN=$GH_BIN_UPLOAD_PW
  update_github
fi

if [[ "$change_webpage" = "True" ]]; then
    update_webpage
fi
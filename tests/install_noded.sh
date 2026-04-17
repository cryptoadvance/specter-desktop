#!/bin/bash
# fail early
set -o pipefail

# change to the directory the script is located in
cd "$( dirname "${BASH_SOURCE[0]}" )/."

function checkout {
    node_impl=$1 # either bitcoin or elements

    # Clone bitcoind if it doesn't exist, or update it if it does
    # (copied from HWI)
    node_setup_needed=false
    if [ ! -d "./${node_impl}/.git" ]; then
        echo "    --> cloning $node_impl"
        if [ "$node_impl" = "elements" ]; then
            clone_url=https://github.com/ElementsProject/elements.git
        elif [ "$node_impl" = "bitcoin" ]; then
            clone_url=https://github.com/bitcoin/bitcoin.git
        else
            echo "unknown node_impl $node_impl"
            exit 1
        fi
        git clone $clone_url
        return 1
    fi
    return 0
}

function maybe_update {
    node_impl=$1 # either bitcoin or elements
    # Determine if we need to pull. From https://stackoverflow.com/a/3278427
    UPSTREAM=origin/master
    LOCAL=$(git describe --all | sed 's/heads\///' | sed 's/tags\///') # gives either a tag or "master" 
    cd ..
    PINNED=$(calc_pytestinit_nodeimpl_version $node_impl)
    cd bitcoin

    # the version in pyproject.toml is (also) used to check the version via getnetworkinfo()["subversion"]
    # However, this might not be a valid git rev. So we need another way to specify the git-rev used
    # as we want to be able to test against specific commits
    if [ -f ../${node_impl}_gitrev_pinned ]; then
        PINNED=$(cat ../${node_impl}_gitrev_pinned)
    fi

    if [ -z $PINNED ]; then
        REMOTE=$(git rev-parse "$UPSTREAM")
        BASE=$(git merge-base @ "$UPSTREAM")
        if [ "$LOCAL" = "$REMOTE" ]; then
            echo "Up-to-date"
        elif [ "$LOCAL" = "$BASE" ]; then
            git pull
            git reset --hard origin/master
            return 1
        fi
    else
        if [ "$LOCAL" = "$PINNED" ]; then
            echo "    --> Pinned: $PINNED! Checkout not needed!"
        else
            echo "    --> Pinned: $PINNED! Checkout needed!"
            git fetch
            git checkout $PINNED
            return 1
        fi
    fi
    if [ -f ./tests/${node_impl}/src/${node_impl}d ]; then
        return 0
    else
        return 1
    fi
}

function calc_pytestinit_nodeimpl_version {

    # returns the version of $node_impl from pyproject.toml from a line which looks like:
    # addopts = --bitcoind-version v22.0 --elementsd-version v0.20.99
    # special treatments for bitcoin and elements necessary, see below
    local node_impl=$1
    if cat ../pyproject.toml | grep -q "${node_impl}d-version" ; then
        # in this case, we use the expected version from the test also as the tag to be checked out
        # i admit that this is REALLY ugly. Happy for any recommendations to do that more easy
        PINNED=$(cat ../pyproject.toml | grep "addopts = " | ${grep} -oP "${node_impl}d-version \K\S+" | cut -d'"' -f1)
       
        if [ "$node_impl" = "elements" ]; then
            # in the case of elements, the tags have a "elements-" prefix
            PINNED=$(echo "$PINNED" | sed 's/v//' | sed 's/^/elements-/')
        fi
        if [ "$node_impl" = "bitcoin" ]; then
            # in the case of bitcoin, the binary-version-artifacts are missing a ".0" at the end which we remove here
            PINNED=$(echo "$PINNED" | sed 's/..$//')
        fi
    fi
    echo $PINNED
}

function build_node_impl {
    node_impl=$1 # either bitcoin or elements
    nodeimpl_setup_needed=$2
    
    if [ "$nodeimpl_setup_needed" = 1 ] ; then
        echo "    --> Autogen & Configure necessary"
        # Build dependencies. This is super slow, but it is cached so it runs fairly quickly.
        cd contrib
        # This is hopefully fullfilles (via .travis.yml most relevantly)
        # sudo apt install make automake cmake curl g++-multilib libtool binutils-gold bsdmainutils pkg-config python3 patch
        
        if [ $(uname) = "Darwin" ]; then
            brew install berkeley-db@4
            brew link berkeley-db4 --force || :
        fi
		echo "    --> Building db4"
        ./install_db4.sh $(pwd)
        echo "    --> Finishing db4"
        ls -l
        cd ..
        echo "    --> Setup needed. Starting autogen"
        ./autogen.sh
        echo "    --> Starting configure"
        export BDB_PREFIX="$(pwd)/contrib/db4"
        echo "        BDB_PREFIX=$BDB_PREFIX"
        # This is for reducing mem-footprint as for some reason cirrus fails even though it has 4GB Mem
        # CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2"
        
        if [ "$node_impl" = "elements" ]; then
            ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include"
        elif [ "$node_impl" = "bitcoin" ]; then
            ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include" CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2" --with-miniupnpc=no --without-gui --disable-zmq --disable-tests --disable-bench --with-libs=no --with-utils=no
        else
            echo "unknown node_impl $node_impl"
            exit 1
        fi
    else
        echo "    --> Skipping Autogen & Configure"
    fi
    export BDB_PREFIX="$(pwd)/contrib/db4"
    BDB_CFLAGS="-I${BDB_PREFIX}/include"
    # optimizing for speed would use the maximum threads available:
    #make -j$(nproc)
    # but we're optimizing for mem-allocation. 1 thread is quite slow, let's try 4 (we have 4GB and need to find the sweet-spot)
    make -j2
    cd ../.. #travis is sourcing this script
    echo "    --> Finished build $node_impl"


}

function sub_help {
    echo "This script will result in having bitcoind or elementsd binaries, either by binary download or via compilation"
    echo "Do one of these:"
    echo "$ ./install_node.sh --bitcoin binary"
    echo "$ ./install_node.sh --bitcoin compile"
    echo "$ ./install_node.sh --elements binary"
    echo "$ ./install_node.sh --elements compile"
    echo "For more context, see https://github.com/cryptoadvance/specter-desktop/blob/master/docs/development.md#how-to-run-the-tests"
}

function check_compile_prerequisites {
    if [ $(uname) = "Darwin" ]; then
        echo "    --> No binary prerequisites checking for MacOS, GOOD LUCK!"
	#brew install automake berkeley-db4 libtool boost miniupnpc pkg-config python qt libevent qrencode sqlite
    else
	    REQUIRED_PKGS="build-essential libtool autotools-dev automake pkg-config bsdmainutils python3 autoconf"
	    REQUIRED_PKGS="$REQUIRED_PKGS libevent-dev libevent-dev libboost-dev libboost-system-dev libboost-filesystem-dev libboost-test-dev bc nodejs npm libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb"
	    REQUIRED_PKGS="$REQUIRED_PKGS wget"
	    for REQUIRED_PKG in $REQUIRED_PKGS; do
	        PKG_OK=$(dpkg-query -W --showformat='${Status}\n' $REQUIRED_PKG|grep "install ok installed")
	        echo Checking for $REQUIRED_PKG: $PKG_OK
	        if [ "" = "$PKG_OK" ]; then
	            echo "No $REQUIRED_PKG. Setting up $REQUIRED_PKG."
	            echo "WARNING: THIS SHOULD NOT BE NECESSARY, PLEASE FIX!"
	            apt-get --yes install $REQUIRED_PKG 
	        fi
	    done
    fi
}

function check_binary_prerequisites {
    if [ $(uname) = "Darwin" ]; then
        if brew list --versions grep &>/dev/null; then
            grep=ggrep
        else
            echo "install grep via brew install grep"
            exit 1
        fi
        echo "    --> No FURTHER binary prerequisites checking for MacOS, GOOD LUCK!"

    else
        REQUIRED_PKGS="wget"
        for REQUIRED_PKG in $REQUIRED_PKGS; do
            PKG_OK=$(dpkg-query -W --showformat='${Status}\n' $REQUIRED_PKG|grep "install ok installed")
            echo Checking for $REQUIRED_PKG: $PKG_OK
            if [ "" = "$PKG_OK" ]; then
                echo "No $REQUIRED_PKG. Setting up $REQUIRED_PKG."
                echo "WARNING: THIS SHOULD NOT BE NECESSARY, PLEASE FIX!"
                apt-get --yes install $REQUIRED_PKG 
            fi
        done
        grep=grep
    fi
}

function sub_compile {
    START=$(date +%s.%N)
    check_compile_prerequisites
    node_impl=$1
    echo "    --> install_node.sh Start $(date) (compiling for $node_impl)"
    echo "        checkout ..."
    checkout $node_impl
    cd $node_impl
    maybe_update $node_impl
    update=$?
    build_node_impl $node_impl $update
    echo "    --> Listing binaries"
    if [ $(uname) = "Darwin" ]; then
    	find tests/${node_impl}/src -maxdepth 1 -type f -perm +111 -exec ls -ld {} \;
    else
	    find tests/${node_impl}/src -maxdepth 1 -type f -executable -exec ls -ld {} \;
    fi
    END=$(date +%s.%N)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_node.sh End $(date) took $DIFF"
}

# -----------------------------------------------------------------------------
# Release signing trust anchors for GPG defense-in-depth verification.
#
# These fingerprints (and the SHA256 trust anchors committed in
# tests/bitcoin_SHA256SUMS / tests/elements_SHA256SUMS) are the reason this
# script exists in its hardened form: CI uses `save-always: true` caches, so
# a single poisoned fetch would persist across every future run if the
# verification path were ever skipped. verify_binary() MUST be invoked on
# both cache miss (fresh download) AND cache hit (restore), and MUST abort
# non-zero on any mismatch.
#
# Builder keys for bitcoin-core releases are published at:
#   https://github.com/bitcoin-core/guix.sigs/tree/main/builder-keys
# The elements signing key was fetched from:
#   hkps://keyserver.ubuntu.com  (search 0x2F2A88D7F8D68E87)
# -----------------------------------------------------------------------------

# Pinned release signing keys (fingerprints). The committed SHA256SUMS files
# in tests/ are the primary trust anchor; the GPG step below re-validates the
# upstream chain when the network is reachable.
BITCOIN_RELEASE_KEYS=(
    "E777299FC265DD04793070EB944D35F9AC3DB76A"  # fanquake <fanquake@gmail.com>
    "152812300785C96444D3334D17565732E08E5E41"  # achow101 / Ava Chow
)
ELEMENTS_RELEASE_KEYS=(
    "8CC974D9CFD034DCEED213B02A57E0A610D7F19C"  # Steven Roose <steven@stevenroose.org>
)

# Compute the sha256 of a file in a cross-platform way.
# Usage: sha256_of <file>
function sha256_of {
    local f=$1
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$f" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$f" | awk '{print $1}'
    else
        echo "ERROR: neither sha256sum nor shasum found" >&2
        return 127
    fi
}

# Look up the expected sha256 for ${basename_of_artifact} from the committed
# trust anchor file tests/${node_impl}_SHA256SUMS. Comment lines (starting
# with '#') in the trust anchor are ignored so the provenance preamble does
# not interfere.
# Usage: expected_sha_for <node_impl> <artifact_basename>
function expected_sha_for {
    local node_impl=$1
    local artifact=$2
    local trust_file=""
    # tests/install_noded.sh cd's to its own dir at the top of the file, so
    # the trust anchors live one directory up from the usual CWD
    # (./${node_impl}) and sometimes in the CWD itself, depending on whether
    # verify_binary is called before or after we cd into ./${node_impl}.
    if [ -f "./${node_impl}_SHA256SUMS" ]; then
        trust_file="./${node_impl}_SHA256SUMS"
    elif [ -f "../${node_impl}_SHA256SUMS" ]; then
        trust_file="../${node_impl}_SHA256SUMS"
    else
        echo "ERROR: trust anchor tests/${node_impl}_SHA256SUMS not found" >&2
        return 2
    fi
    # Format: <hex>  <filename>
    grep -v '^[[:space:]]*#' "$trust_file" \
        | awk -v f="$artifact" '$2 == f {print $1; exit}'
}

# Import release signing keys into a throw-away GNUPGHOME and GPG-verify
# ${sumsfile} against ${sigfile}. Returns 0 on good signature, non-zero on
# anything else (including no network, missing gpg, bad sig). Callers MUST
# still compare ${sumsfile} to the committed trust anchor — this GPG step is
# defense in depth, not the sole trust anchor.
# Usage: gpg_verify_sums <node_impl> <sumsfile> <sigfile>
function gpg_verify_sums {
    local node_impl=$1
    local sumsfile=$2
    local sigfile=$3
    if ! command -v gpg >/dev/null 2>&1; then
        echo "    --> WARNING: gpg not installed; skipping upstream GPG re-verify (committed SHA256SUMS trust anchor still enforced)"
        return 0
    fi
    local tmp_gnupg
    tmp_gnupg=$(mktemp -d -t specter-gnupg-XXXXXX) || return 1
    # shellcheck disable=SC2064
    trap "rm -rf '$tmp_gnupg'" RETURN
    export GNUPGHOME="$tmp_gnupg"
    chmod 700 "$tmp_gnupg"
    local keys=()
    if [ "$node_impl" = "bitcoin" ]; then
        keys=("${BITCOIN_RELEASE_KEYS[@]}")
    elif [ "$node_impl" = "elements" ]; then
        keys=("${ELEMENTS_RELEASE_KEYS[@]}")
    fi
    local imported=0
    for fpr in "${keys[@]}"; do
        # Try keys.openpgp.org first, then keyserver.ubuntu.com.
        if curl -fsSL "https://keys.openpgp.org/vks/v1/by-fingerprint/${fpr}" 2>/dev/null \
            | gpg --import 2>/dev/null; then
            imported=$((imported + 1))
            continue
        fi
        if curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x${fpr}&options=mr" 2>/dev/null \
            | gpg --import 2>/dev/null; then
            imported=$((imported + 1))
        fi
    done
    if [ "$imported" -eq 0 ]; then
        echo "    --> WARNING: could not fetch any ${node_impl} release signing keys; skipping upstream GPG re-verify"
        unset GNUPGHOME
        return 0
    fi
    # Bitcoin Core SHA256SUMS.asc carries signatures from many maintainers.
    # gpg --verify exits non-zero when ANY signature's key is missing, even
    # if others verify successfully.  We only import a subset of keys, so
    # the raw exit code is unreliable.  Instead, use --status-fd to check
    # for at least one VALIDSIG whose primary-key fingerprint we trust.
    #
    # VALIDSIG format (last field is always the primary key fingerprint,
    # even when the signature was made by a subkey):
    #   VALIDSIG <sign_fpr> <date> <ts> ... <primary_fpr>
    # GOODSIG uses the signing subkey ID, which may differ from the primary
    # fingerprint we pin — so VALIDSIG is the correct field to match.
    local status_out
    if [ -n "$sigfile" ] && [ -f "$sigfile" ]; then
        status_out=$(gpg --status-fd 1 --verify "$sigfile" "$sumsfile" 2>/dev/null)
    else
        # Clearsigned (elements case): verify in-place.
        status_out=$(gpg --status-fd 1 --verify "$sumsfile" 2>/dev/null)
    fi
    local found_good=0
    for fpr in "${keys[@]}"; do
        # Match VALIDSIG line whose last field (primary fingerprint) equals ours.
        if echo "$status_out" | grep -q "VALIDSIG.*${fpr}"; then
            found_good=1
            echo "    --> GPG: valid signature traced to primary key ${fpr}"
            break
        fi
    done
    unset GNUPGHOME
    if [ "$found_good" -eq 0 ]; then
        echo "    --> WARNING: no VALIDSIG from a trusted primary key found in GPG status output"
        echo "    --> Status output: $status_out"
        return 1
    fi
    return 0
}

# Verify a binary artifact (tarball) against the committed trust anchor.
# Aborts the script with exit 2 on any mismatch.
# Usage: verify_binary <node_impl> <path_to_binary_file>
function verify_binary {
    local node_impl=$1
    local binary_path=$2
    if [[ ! -f "$binary_path" ]]; then
        echo "ERROR: verify_binary: $binary_path does not exist" >&2
        exit 2
    fi
    local artifact
    artifact=$(basename "$binary_path")
    local expected
    expected=$(expected_sha_for "$node_impl" "$artifact")
    if [ -z "$expected" ]; then
        echo "ERROR: verify_binary: no trusted sha256 entry for '$artifact' in tests/${node_impl}_SHA256SUMS" >&2
        exit 2
    fi
    local actual
    actual=$(sha256_of "$binary_path") || exit 2
    if [ "$expected" != "$actual" ]; then
        echo "ERROR: verify_binary: sha256 mismatch for $artifact" >&2
        echo "       expected $expected" >&2
        echo "       actual   $actual" >&2
        echo "       This is a trust violation. Aborting." >&2
        exit 2
    fi
    echo "    --> verify_binary: OK ($artifact sha256=$expected)"
}

function sub_binary {
    node_impl=$1
    echo "    --> install_noded.sh Start $(date) (binary) for node_impl $node_impl"
    START=$(date +%s)
    check_binary_prerequisites
    # todo: Parametrize this
    version=$(calc_pytestinit_nodeimpl_version $node_impl)
    echo "    --> install version $version"
    # remove the v-prefix
    version=$(echo $version | sed -e 's/v//')
    if [ $(uname) = "Darwin" ]; then
        binary_file=${node_impl}-${version}-osx64.tar.gz
    else
        binary_file=${node_impl}-${version}-x86_64-linux-gnu.tar.gz
    fi

    # The tarball lives inside ./${node_impl}/ so that it is captured by the
    # cache (which covers ./tests/${node_impl}/) and re-verified on every
    # cache restore. This is the whole point of the hardened flow — see the
    # "save-always backdoor" rationale at the top of the file.
    # Clean up a broken symlink from a partial cache restore (the workflow
    # caches ./tests/${node_impl}-* as well, but be defensive).
    if [[ -L "./${node_impl}" && ! -e "./${node_impl}" ]]; then
        echo "    --> cleaning up dangling symlink ./${node_impl}"
        rm -f "./${node_impl}"
    fi
    mkdir -p "./${node_impl}"
    local cached_tarball="./${node_impl}/${binary_file}"

    if [[ -f "$cached_tarball" ]]; then
        echo "    --> cache hit: found existing ${cached_tarball}, re-verifying"
        verify_binary "$node_impl" "$cached_tarball"
    else
        echo "    --> cache miss: downloading ${binary_file}"
        if [ "$node_impl" = "elements" ]; then
            # elements publishes a clearsigned SHA256SUMS.asc only
            ( cd "./${node_impl}" && \
                wget -q "https://github.com/ElementsProject/elements/releases/download/${version}/${binary_file}" && \
                wget -q "https://github.com/ElementsProject/elements/releases/download/${version}/SHA256SUMS.asc" )
            gpg_verify_sums "$node_impl" "./${node_impl}/SHA256SUMS.asc" "" \
                || { echo "ERROR: upstream GPG verification failed for elements SHA256SUMS.asc" >&2; exit 2; }
        fi
        if [ "$node_impl" = "bitcoin" ]; then
            ( cd "./${node_impl}" && \
                wget -q "https://bitcoincore.org/bin/bitcoin-core-${version}/${binary_file}" && \
                wget -q "https://bitcoincore.org/bin/bitcoin-core-${version}/SHA256SUMS" && \
                wget -q "https://bitcoincore.org/bin/bitcoin-core-${version}/SHA256SUMS.asc" )
            gpg_verify_sums "$node_impl" "./${node_impl}/SHA256SUMS" "./${node_impl}/SHA256SUMS.asc" \
                || { echo "ERROR: upstream GPG verification failed for bitcoin SHA256SUMS.asc" >&2; exit 2; }
        fi
        # Primary trust anchor: committed tests/${node_impl}_SHA256SUMS.
        verify_binary "$node_impl" "$cached_tarball"
    fi

    # Extract into ./${node_impl}-${version}/ (tarballs ship that layout).
    # Leave the tarball in place inside ./${node_impl}/ to be reused on
    # subsequent cache hits (that directory becomes a symlink below, so we
    # copy the tarball out to a sibling and re-plant it after the symlink).
    local tarball_basename="${binary_file}"
    cp "$cached_tarball" "./${tarball_basename}.verified"
    tar -xzf "$cached_tarball"
    if [[ -d ./"$node_impl" ]]; then
        if [[ -d ./"$node_impl"/src ]]; then
            mv ./"$node_impl" ./"$node_impl"-src
        else
            rm -rf ./"$node_impl"
        fi
    fi
    rm -f "$node_impl"
    ln -s ./"$node_impl"-${version} "$node_impl"
    # Re-plant the verified tarball inside the (now-symlinked) cached dir so
    # the next cache restore can re-verify it.
    mv "./${tarball_basename}.verified" "./${node_impl}/${binary_file}"

    echo "    --> Listing binaries"
    if [ $(uname) = "Darwin" ]; then
        find ./"$node_impl"/bin -maxdepth 1 -type f -perm +111 -exec ls -ld {} \;
    else
        find ./"$node_impl"/bin -maxdepth 1 -type f -executable -exec ls -ld {} \;
    fi
    echo "    --> checking for ${node_impl}d"
    test -x ./${node_impl}/bin/${node_impl}d || exit 2

    # Final defense-in-depth: re-verify the tarball one more time so that
    # tampering between extract and exit is caught as well.
    verify_binary "$node_impl" "./${node_impl}/${binary_file}"

    echo "    --> Finished installing ${node_impl}d binary"
    END=$(date +%s)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_noded.sh End $(date) took $DIFF seconds"
}


function parse_and_execute() {
  if [[ $# = 0 ]]; then
    sub_help
    exit 0
  fi 

  while [[ $# -gt 0 ]]
  do
  arg="$1"
  case $arg in
      "" | "-h" | "--help")
        sub_help
        shift
        ;;
      --debug)
        set -x
        DEBUG=true
        shift
        ;;
      --bitcoin)
        node_impl=bitcoin
        shift
        ;;
      --elements)
        node_impl=elements
        shift
        ;;
      help)
        sub_help
        shift
        ;;
      compile)
        sub_compile $node_impl || exit 2
        shift
        ;;
      binary)
        sub_binary $node_impl || exit 2
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
}

parse_and_execute $@

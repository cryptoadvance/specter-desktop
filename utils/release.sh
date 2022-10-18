#!/bin/bash

# Replacing MacOS utilities with GNU core utilities to make script more robust
# See: https://apple.stackexchange.com/questions/69223/how-to-replace-mac-os-x-utilities-with-gnu-core-utilities
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew ls --versions coreutils > /dev/null; 
    exitCode=$? 
    if [[ $exitCode == 0 ]]; then
      echo "Coreutils are installed via Homebrew, prepending PATH to use GNU core utilities over MacOS utilities."
      export PATH="/usr/local/opt/coreutils/libexec/gnubin:$PATH"
    else
      echo "GNU core utilities not installed. Run brew install coreutils"
    fi
fi

ask_yn() {
   while true; do
        read -p "Is this correct [y/n]" yn
        case $yn in
            [Yy]* ) return 0 ;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done 
}

while [[ $# -gt 0 ]]
do
key="$1"
command="main"
case $key in
    wait_on_master)
    command=wait_on_master
    shift
    ;;
    --help)
    help
    shift
    exit 0
    ;;
    --release-notes)
    RELEASE_NOTES="yes"
    shift # past value
    ;;
    --dev)
    DEV="yes"
    shift
    ;;
    --new-version)
    new_version=$2
    shift
    shift
    ;;
    --tag)
    TAG="yes"
    shift
    ;;
    --debug)
    set -x
    shift # past argument
    ;;
    *)    # unknown option
    POSITIONAL="$1" # save it in an array for later
    shift # past argument
    ;;
esac
done

function help() {
    # echo HERE_DOC
    # ...
    echo "not yet implemented"
}

function main() {
    # Sed is used as there can be whitespaces 
    if ! [ "$(git remote -v | grep upstream | grep 'git@github.com:cryptoadvance/specter-desktop.git' |  wc -l | sed -e 's/\s*//')" = "2" ]; then
        echo "    --> You don't have the correct upstream-remote. You need this to release. Please do this:"
        echo "git remote add upstream git@github.com:cryptoadvance/specter-desktop.git "
        exit 2
    fi

    if ! [ "$(git remote -v | grep origin | grep 'git@github.com:' | wc -l)" = "2" ]; then
        echo "    --> You don't have a reasonable origin-remote. You need this to release (especially with --dev). Please add one!"
        exit 2
    fi
    
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [ "$current_branch" != "master" ]; then
        echo "You're currently not on the master-branch, exiting"
        exit 2
    fi

    echo "    --> Fetching all tags ..."
    git fetch upstream --tags
    echo "    --> git pull upstream master"
    git pull upstream master

    if [[ -z "$new_version" ]]; then
        echo "What should be the new version? Type in please (e.g. v0.9.3 ):"
        read new_version
    fi

    if ! [[ $new_version =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)(-([0-9A-Za-z-]+))?$ ]]; then 
        echo "version $new_version Does not match the pattern!"
        exit 1; 
    fi

    if [[ -n "$RELEASE_NOTES" ]]; then


        if [ -z $GH_TOKEN ]; then
            echo "Your github-token is missing. Please export them like:"
            echo "export GH_TOKEN="
            exit 2
        fi

        latest_version=$(git tag -l "v*" | grep -v 'pre' | grep -v 'dev' | sort -V | tail -1)

        echo "    --> The latest version is $latest_version. "
        if ! ask_yn ; then
            echo "Ok, then you type in the latest_version:"
            read latest_version
            if ! [[ $new_version =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)(-([0-9A-Za-z-]+))?$ ]]; then 
                echo "Does not match the pattern!"
                exit 1; 
            fi
        fi

        echo "Here are the release-notes:"
        echo "--------------------------------------------------"
        echo "# Release Notes" > docs/new_release_notes.md
        echo "" >> docs/new_release_notes.md
        echo "## ${new_version} $(date +'%B %d, %Y')" >> docs/new_release_notes.md
        docker run registry.gitlab.com/cryptoadvance/specter-desktop/github-changelog:latest --github-token $GH_TOKEN --branch master cryptoadvance specter-desktop $latest_version | sort >> docs/new_release_notes.md
        echo "" >> docs/new_release_notes.md
        

        cat docs/new_release_notes.md
        echo "--------------------------------------------------"

        cp docs/release-notes.md docs/release-notes.md.orig
        sed -i -e '1,2d' docs/release-notes.md.orig # Assuming the release-Notes start with # Release Notes\n
        cat docs/new_release_notes.md docs/release-notes.md.orig >  docs/release-notes.md
        rm docs/release-notes.md.orig docs/new_release_notes.md

        echo "Please check your new File and modify as you find approriate!"
        echo "We're waiting here ..."
        echo "    --> Should we create a PR-branch now? "

        if ! ask_yn ; then
            echo "break"
            #git checkout docs/release-notes.md
            exit 2
        fi

        echo "    --> Creating branch ${new_version}_release_notes "
        git checkout -b ${new_version}_release_notes
        git add docs/release-notes.md
        git commit -m "adding release_notes for $new_version"
        git push --set-upstream origin ${new_version}_release_notes

        echo "Now go ahead and make your PR:"
        echo "https://github.com/cryptoadvance/specter-desktop/pulls"
        exit 0
    fi



    if [[ -n "$TAG" ]]; then

        echo "    --> Should i now create the tag and push the version $new_version ?"
        if [ -z $DEV ]; then
            echo "    --> This will push to your origin-remote!"
        else
            echo "    --> THIS WILL PUSH TO THE UPSTREAM-REMOTE!"
            if ! ask_yn ; then
                echo "break"
                exit 2
            fi
        fi
        
        git tag $new_version 
        if [ -z $DEV ]; then
            git push origin $new_version
        else
            git push upstream $new_version
        fi
    fi

}

function wait_on_master() {
    echo "# check status of masterbranch ..."
    i=0
    # First, wait on the check-runs to be completed:
    for i in {1..5} ; do
        current_state=$(curl -s https://api.github.com/repos/cryptoadvance/specter-desktop/commits/master/check-runs)
        different_states=$(echo $current_state | jq -r '.check_runs[] | select(.status == "completed") | .status' | uniq | wc -l)
        status=$(echo $current_state | jq -r '.check_runs[] | select(.status == "completed") | .status' | uniq)
    
        if [[ "$different_states" == 1 ]] && [[ "$status" == "completed" ]] ; then
            break
        fi
        echo "# Builds still running. Will check again in 5 seconds."
        sleep 5
    done

    # Now check all the runs and make sure there are all green:
    current_state=$(curl -s https://api.github.com/repos/cryptoadvance/specter-desktop/commits/master/check-runs)
    different_conclusions=$(echo $current_state | jq -r '.check_runs[] | select(.conclusion == "success") | .conclusion' | uniq | wc -l)
    conclusion=$(echo $current_state | jq -r '.check_runs[] | select(.conclusion == "success") | .conclusion' | uniq)
    
    # We only have one conclusion over all runs:
    if [ $different_conclusions -gt 1 ] ; then
        echo "# different_conclusions: $different_conclusions"
        echo "# Seems that master is not green. Exiting 1"
        exit 1
    fi
    # ... and that conclusion is "success"
    if [[ "$conclusion" == "success" ]]; then
        echo "# Great, conclusion is success! Exiting 0"
        exit 0
    fi

    echo "# ERROR: I'm confused. This should not happened, exiting 99"
    echo "# conclusion = $conclusion"
    #echo $current_state
    exit 99
}

$command
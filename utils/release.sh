#!//bin/bash

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


function main() {

    if ! [ "$(git remote -v | grep upstream | grep 'git@github.com:cryptoadvance/specter-desktop.git' | wc -l)" = "2" ]; then
        echo "    --> You don't have the correct upstream-remote. You need this to release. Please do this:"
        echo "git remote add upstream git@gitlab.com:cryptoadvance/specter-cloud.git "
        exit 2
    fi

    if ! [ "$(git remote -v | grep origin | grep 'git@github.com:' | wc -l)" = "2" ]; then
        echo "    --> You don't have a reasonable origin-remote. You need this to release (especially with --dev). Please add one!"
        exit 2
    fi

    echo "    --> Fetching all tags ..."
    git fetch upstream --tags

    current_branch=$(git rev-parse --abbrev-ref HEAD)

    if [ "$current_branch" != "master" ]; then
        echo "You're currently not on the master-branch, so we assume this will get a PR"
        git fetch upstream master
        PR_MODE=yes
        if ! git diff master..${current_branch} --exit-code > /dev/null; then
            echo "You current branch is also not similiar to master."
            echo "should i merge master?"
            if ! ask_yn ; then
                echo "break"
                exit 2
            fi
            git merge master
        fi
    fi

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

        echo "latest_version is $latest_version. "

        echo "    --> The latest version is $latest_version. "
        echo "    --> We'll create the release-notes based on that."
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
        echo "## ${new_version} $(date +'%B %d, %Y')" > docs/new_release_notes.md
        docker run registry.gitlab.com/cryptoadvance/specter-desktop/github-changelog:latest --github-token $GH_TOKEN --branch master cryptoadvance specter-desktop $latest_version | sort >> docs/new_release_notes.md
        echo "" >> docs/new_release_notes.md
        cat docs/new_release_notes.md
        echo "--------------------------------------------------"

        cp docs/release-notes.md docs/release-notes.md.orig
        cat docs/new_release_notes.md docs/release-notes.md.orig >  docs/release-notes.md
        rm docs/release-notes.md.orig docs/new_release_notes.md

        echo "Please check your new File and modify as you find approriate!"
        echo "We're waiting here ..."

        echo "    --> Should we commit and push that (to origin) now? "

        if ! ask_yn ; then
            echo "break"
            echo "Rolling back release_notes.md ..."
            git checkout docs/release-notes.md
            exit 2
        fi

        git add docs/release-notes.md
        git commit -m "adding release_notes to $new_version"
        git push origin

        echo "Now go ahead and make your PR:"
        echo "https://github.com/cryptoadvance/specter-desktop/compare"
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
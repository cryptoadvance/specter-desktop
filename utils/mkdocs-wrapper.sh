#!/bin/bash

# netlify is configured to use the utils-directory as base directory
# This prevents that it's using the requirements-txt and a lot of issues
# So in order to make the script work the exact same in both cases,
# we first change the directory one up, no matter from where this script
# has been executed from.
cd "$( dirname "${BASH_SOURCE[0]}" )/.."

echo "    --> Starting mkdocs-wrapper.sh"

# This is mainly used by netlify where we're using the free starter-plan
# Checkout https://github.com/cryptoadvance/specter-desktop/pull/1463
# for a more birds eye view of this script.

# The nelify settings for this to work need to be:
# * Repository: github.com/cryptoadvance/specter-desktop
# * Base directory: Not set
# * Build command: ./utils/mkdocs-wrapper.sh build
# * Publish directory: site
# In the Environment Variables, you have to set:
# PYTHON_VERSION 3.10

# We're using mkdocs for creating the static pages
# We don't pin this dependency as this is not relevant for either testing or
# production. Therefore it's easier to simply let it upgrade automatically:
echo "    Running pip install mkdocs mkdocs-video  mdx_truly_sane_lists" 
pip3 install mkdocs mkdocs-video  mdx_truly_sane_lists
# At the sime of this comment, we had: mkdocs==1.2.3



# We want the README-md file in the root-folder for people browsing github
# but we also want it for people browsing https://docs.specter.solutions/desktop
# So for the second case, we copy it there and change all the links
if [ "$1" = "build" ]; then
    echo "    --> Copying and adjusting README.md"
    cp README.md docs
    sed -i 's/docs\///g' docs/README.md
    sed -i 's/Checkout our Documentation at.*//' docs/README.md
    sed -i 's/\.\.\/README.md/README.m/g' docs/*.md
fi

echo "    --> now running mkdocs $1 $2"

mkdocs $1 $2

# As netlify expects the site-dir in its basedir (./utils, see above) we need 
# to mv it
mv site ./utils/site

# Potentially, we could rollback here the changes but that would be anoying if you want 
# to edit files.

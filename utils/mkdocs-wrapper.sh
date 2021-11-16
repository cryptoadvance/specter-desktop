#!/bin/bash

# We want the README-md file in the root-folder for people browsing github
# but we also want it for people browsing https://docs.specter.solutions/desktop

# So for the second case, we copy it there and change all the links

# This is mainly used by netlify

# We don't pin this dependency as this is not relevant for either testing or
# production. Therefore it's easier to simply let it upgrade automatically:
pip3 install mkdocs 
# At the sime of this comment, we had: mkdocs==1.2.3

if [ "$1" = "build" ]; then
    cp README.md docs
    sed -i 's/docs\///g' docs/README.md
    sed -i 's/\.\.\/README.md/README.m/g' docs/*.md

fi


mkdocs $1 $2

# Potentially, we could rollback here the changes but that would be anoying if you want 
# to edit files.
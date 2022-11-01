#!/bin/bash

cd .. ; ./utils/mkdocs-wrapper.sh build; mv site netlify/site;
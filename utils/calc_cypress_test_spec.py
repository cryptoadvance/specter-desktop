#!/usr/bin/env python3
" Some tooling for calculating dependencies for cypress_spec_files e.g. ready to pass to cypress --spec"

import json
import sys
import click
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--debug/--no-debug")
@click.option(
    "--run/--no-run",
    default=False,
    help="--run for creating a run list, otherwise create-list",
)
@click.option("--delimiter", default=",", help="the delimiter")
@click.argument("spec_file")
def execute(debug, run, delimiter, spec_file):
    with open("cypress.json") as json_file:
        data = json.load(json_file)

    spec_create_list = []
    spec_run_list = []
    hit = False
    for my_file in data["testFiles"]:
        if my_file == spec_file:
            hit = True
        if hit:
            logger.debug(f"iterating {my_file} adding to run_list")
            spec_run_list.append("./cypress/integration/" + my_file)
        else:
            logger.debug(f"iterating {my_file} adding to create_list")
            spec_create_list.append("./cypress/integration/" + my_file)

    if run:
        print(delimiter.join(spec_run_list))
    else:
        print(delimiter.join(spec_create_list))


if __name__ == "__main__":
    execute()

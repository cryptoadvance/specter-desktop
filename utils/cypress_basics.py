#!/usr/bin/env python3
"""
Returns a string of a list of basic test files (such as configuring the nodes) on which other more specialised tests depend on.
This string is picked up by a subprocess in test-cypress.sh
"""

import json
import click
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
def execute():
    with open("cypress_basics.json") as json_file:
        data = json.load(json_file)
    spec_run_list = []
    for file in data["testFiles"]:
        spec_run_list.append("./cypress/integration/" + file)
    click.echo(",".join(spec_run_list))


if __name__ == "__main__":
    execute()

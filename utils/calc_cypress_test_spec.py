#!/usr/bin/env python3
" accumulates all cypress_spec_files excluding the specified one ready to pass to cypress --spec"

import json
import sys

with open("cypress.json") as json_file:
    data = json.load(json_file)

reverse = False
if len(sys.argv) > 2 and sys.argv[2] == "--reverse":
    reverse = True

spec_create_list = []
spec_run_list = []
hit = False
for spec_file in data["testFiles"]:
    if spec_file == sys.argv[1]:
        hit = True
    if not hit:
        spec_create_list.append("./cypress/integration/" + spec_file)
    else:
        spec_run_list.append("./cypress/integration/" + spec_file)


if reverse:
    print(",".join(spec_run_list))
else:
    print(",".join(spec_create_list))

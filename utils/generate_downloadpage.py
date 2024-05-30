import datetime
import json
import logging
import re
import sys

import markdown
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.utils import markupsafe


stoh = logging.StreamHandler(sys.stderr)
fmth = logging.Formatter("[%(levelname)s] %(asctime)s %(message)s")
stoh.setFormatter(fmth)

logger = logging.getLogger(__name__)
logger.addHandler(stoh)
logger.setLevel(logging.DEBUG)


def website():
    """generates the two snippets for the website"""
    md = markdown.Markdown(extensions=["meta"])
    env = Environment(
        loader=FileSystemLoader("./templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["markdown"] = lambda text: markupsafe.Markup(md.convert(text))
    env.globals["get_title"] = lambda: md.Meta["title"][0]
    env.trim_blocks = True
    env.lstrip_blocks = True
    date = None
    headers = {"Accept": "application/vnd.github.v3+json"}
    data = json.loads(
        requests.get(
            "https://api.github.com/repos/cryptoadvance/specter-desktop/releases",
            headers=headers,
        ).text
    )
    # Some time-conversion to make formating easier in jinja2
    logger.info(f"  --> preprocessing all releases")
    pre_release_pattern = re.compile(".*-pre[0-9]")  # -(pre)|(dev)[0-9]
    for idx, release in enumerate(data):
        logger.info(f"      processing {release['name']}")
        if pre_release_pattern.match(release["name"]):
            logger.info(f"      marking {release['name']} as pre-release")
            release["is_pre_release"] = True
        else:
            release["published_at"] = datetime.datetime.strptime(
                release["published_at"], "%Y-%m-%dT%H:%M:%SZ"
            )

    current = data[0]
    current["assets_by_os"] = {
        "macos": "not_existing",
        "linux": "not_existing",
        "win": "not_existing",
    }
    logger.info(f"  --> preprocessing current release")
    for asset in current["assets"]:
        logger.info(f"  processing {asset['name']}")
        if asset["browser_download_url"].endswith(".exe"):
            current["assets_by_os"]["win"] = asset
            logger.info(f"    Found win for {asset['name']}")
        if asset["browser_download_url"].endswith(".dmg"):
            current["assets_by_os"]["macos"] = asset
            logger.info(f"    Found macos for {asset['name']}")
        if asset["browser_download_url"].endswith(".tar.gz") and asset[
            "name"
        ].startswith("specter_desktop"):
            current["assets_by_os"]["linux"] = asset
            logger.info(f"    Found linux for {asset['name']}")
        if asset["browser_download_url"].endswith("SHA256SUMS.asc"):
            current["signatures"] = asset
            logger.info(f"    Found signatures")
        if asset["browser_download_url"].endswith("SHA256SUMS"):
            current["hashes"] = asset
            logger.info(f"    Found hashes")
    template = env.get_template("download-page_current.html")
    with open("build/download-page_current.html", "w") as f:
        f.write(template.render(data=data, current=data[0]))
    template = env.get_template("download-page_releases.html")
    # print(data)
    with open("build/download-page_releases.html", "w") as f:
        f.write(template.render(data=data, current=data[0]))

    # download_page final
    template = env.get_template("download-page.html")
    with open("build/download-page.html", "w") as f:
        f.write(template.render(data=data, current=data[0]))


def gh_release_notes(latest_release):
    env = Environment(loader=FileSystemLoader("./templates"))
    template = env.get_template("gh_release-page-v2.md")
    data = {"version": latest_release, "release_notes": ""}
    rn_file = requests.get(
        "https://raw.githubusercontent.com/cryptoadvance/specter-desktop/master/docs/release-notes.md"
    ).text.split("\n")
    logger.info("  --> Creating Release")
    status = "search"
    release_item_counter = 0
    for line in rn_file:
        if status == "search" and line.startswith("##"):
            status = "harvest"
            continue
        if status == "harvest" and not line.strip():
            break
        if status == "search":
            continue

        data["release_notes"] = data["release_notes"] + line + "\n"
        release_item_counter = release_item_counter + 1

    logger.info(f"      {release_item_counter} items added to release_notes")

    print(line)
    with open("build/gh_page.md", "w") as f:
        f.write(template.render(data=data))


if __name__ == "__main__":
    headers = {"Accept": "application/vnd.github.v3+json"}
    latest_release = json.loads(
        requests.get(
            "https://api.github.com/repos/cryptoadvance/specter-desktop/releases/latest",
            headers=headers,
        ).text
    )
    latest_release = latest_release["name"]
    logger.info(latest_release)
    website()
    gh_release_notes(latest_release)

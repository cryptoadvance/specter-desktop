import typing
import strawberry
from typing import List
import json
import os
import logging

logger = logging.getLogger(__name__)


@strawberry.type
class Bookmark:
    url: str
    desc: str
    readlater: str
    annotations: List[str]
    tags: str
    comments: List[str]
    shared: str
    title: str


def get_bookmarks() -> List[Bookmark]:
    logger.info("CALLING get_bookmarks!!")
    with open("src/cryptoadvance/specterext/devhelp/data.json") as json_file:
        data = json.load(json_file)
    listOfBookmarks = []
    for item in data:
        b = Bookmark(
            url=item["url"],
            desc=item["desc"],
            readlater=item["readlater"],
            annotations=[],  # fixme
            tags=item["tags"],
            comments=item["comments"],
            shared=item["shared"],
            title=item["title"],
        )
        listOfBookmarks.append(b)
    return listOfBookmarks

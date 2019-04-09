import html
import time
from urllib.parse import urljoin

import click
import requests
from bs4 import BeautifulSoup, SoupStrainer


class Link:
    def __init__(self, title, url):
        self.title = title
        self.url = url
        self.children = []

    def walk(self):
        def iter_fn(depth, parent, root):
            yield depth, parent, root
            for child in root.children:
                yield from iter_fn(depth + 1, root, child)

        yield from iter_fn(0, None, self)

    def __str__(self):
        def pretty():
            for depth, parent, root in self.walk():
                link_str = "{space} - [{title}]({url})".format(
                    space="    " * depth, title=root.title, url=root.url
                )
                yield link_str

        return "\n".join(pretty())

    def to_bookmark(self):
        # https://msdn.microsoft.com/en-us/ie/aa753582%28v=vs.94%29
        header = (
            "<!DOCTYPE NETSCAPE-Bookmark-file-1>"
            "<!-- This is an automatically generated file.\n"
            "     It will be read and overwritten.\n"
            "     DO NOT EDIT! -->"
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">'
            "<TITLE>Bookmarks</TITLE>"
            "<H1>Bookmarks</H1>"
        )
        timestamp = int(time.time())

        def _to_bookmark(link):
            if link.children:
                return (
                    '<DT><H3 ADD_DATE="{timestamp}" LAST_MODIFIED="{timestamp}">{title}</H3>'
                    "<DL><p>"
                    "{children}"
                    "</DL><p>".format(
                        timestamp=timestamp,
                        title=link.title,
                        children="".join([_to_bookmark(l) for l in link.children]),
                    )
                )
            return '<DT><A HREF="{url}" ADD_DATE="{timestamp}" LAST_MODIFIED="{timestamp}">{title}</A>'.format(
                timestamp=timestamp,
                url=html.escape(link.url),
                title=html.escape(link.title),
            )

        return header + "<DL><p>{children}</DL>".format(
            children="".join([_to_bookmark(l) for l in self.children])
        )


def extract(host, path):
    url = urljoin(host, path)
    bs = BeautifulSoup(
        requests.get(url).text,
        parse_only=SoupStrainer(id="docsToc"),
        features="html.parser",
    )
    children = list(bs.find("div", class_="pi-accordion"))
    root_tag = children[0]

    def handle_tag(tag):
        if tag.name == "a":
            return Link(tag["data-title"], urljoin(host, tag["href"]))
        href = tag.get("href")
        if href:
            href = urljoin(host, href)

        sub_folder = Link(tag["data-title"], href)
        for child in tag.find("div", class_="container").children:
            sub_folder.children.append(handle_tag(child))
        return sub_folder

    root = Link(root_tag["data-title"], urljoin(host, root_tag["href"]))
    for c in children[1:]:
        root.children.append(handle_tag(c))
    return root


@click.command()
def cli():
    """
    extract kubernetes document links.
    """
    base_url = "https://kubernetes.io/"
    root = Link("Kubernetes Documents", urljoin(base_url, "docs"))
    sections = [
        "docs/setup",
        "docs/concepts",
        "docs/tasks",
        "docs/tutorials",
        "docs/reference",
    ]
    for section in sections:
        root.children.append(extract(base_url, section))
    click.echo(root)
    import os

    file_path = os.path.abspath("Kubernetes Documents Bookmarks.html")
    with open(file_path, "wt") as fp:
        fp.write(root.to_bookmark())
    click.echo("Bookmarks exported to " + repr(file_path))

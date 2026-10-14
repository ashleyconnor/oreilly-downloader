import argparse
import json
import posixpath
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

BASE_URL = 'https://learning.oreilly.com'

CONTAINER = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
    <rootfiles>
        <rootfile full-path="{}" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>
"""  # noqa

VOID_ELEMENTS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'source', 'track', 'wbr',
}


class TreeBuilder(HTMLParser):
    """Parse (possibly sloppy) HTML into an ElementTree."""

    def __init__(self):
        super().__init__()
        self.stack = [ET.Element('root')]

    def handle_starttag(self, tag, attrs):
        el = ET.SubElement(self.stack[-1], tag, {k: v or '' for k, v in attrs})
        if tag not in VOID_ELEMENTS:
            self.stack.append(el)

    def handle_endtag(self, tag):
        # implicitly close any unclosed children, ignore stray end tags
        if any(el.tag == tag for el in self.stack[1:]):
            while self.stack.pop().tag != tag:
                pass

    def handle_data(self, data):
        parent = self.stack[-1]
        if len(parent):
            parent[-1].tail = (parent[-1].tail or '') + data
        else:
            parent.text = (parent.text or '') + data


def to_xhtml(s, root_path, path, stylesheets):
    builder = TreeBuilder()
    builder.feed(s.decode('utf-8'))
    builder.close()
    tree = builder.stack[0]
    base = posixpath.dirname(root_path + path)

    for el in tree.iter():
        for attr in ['href', 'src']:
            if (el.get(attr) or '').startswith(root_path):
                el.set(attr, posixpath.relpath(el.get(attr), base))

    for el in tree.iter('svg'):
        for attr in ['viewBox', 'preserveAspectRatio']:
            if attr.lower() in el.attrib:
                el.set(attr, el.attrib.pop(attr.lower()))

    html = tree.find('html')
    if html is None:
        html = ET.Element('html', {
            'xmlns': 'http://www.w3.org/1999/xhtml',
            'xmlns:epub': 'http://www.idpf.org/2007/ops',
        })

        head = ET.SubElement(html, 'head')
        for href in stylesheets:
            ET.SubElement(head, 'link', rel='stylesheet', href=posixpath.relpath(root_path + href, base))
        h1 = tree.find('.//h1')
        if h1 is not None:
            title = ET.SubElement(head, 'title')
            title.text = ''.join(h1.itertext()).strip()

        body = ET.SubElement(html, 'body')
        body.text = tree.text
        body.extend(tree)

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        + ET.tostring(html, encoding='unicode')
    ).encode('utf-8')


def make_getter(jwt):
    headers = {'User-Agent': 'orlydown'}
    if jwt:
        headers['Cookie'] = f'orm-jwt={jwt}'

    def get(url):
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as r:
            return r.read()

    return get


def check_auth(get):
    try:
        get(BASE_URL + '/api/v1/user-preferences/')
        return True
    except urllib.error.HTTPError:
        return False


def fetch_book(book_id, zfh, get, *, delay=0):
    root_path = f'/api/v2/epubs/urn:orm:book:{book_id}/files/'
    html = {}

    def download(result):
        return result, get(result['url'])

    zfh.writestr('mimetype', b'application/epub+zip', compress_type=zipfile.ZIP_STORED)

    url = BASE_URL + root_path
    with ThreadPoolExecutor() as pool:
        while url:
            print(f'fetching {url}')
            data = json.loads(get(url))

            for result, content in pool.map(download, data.get('results', [])):
                path = f'EPUB/{result["full_path"]}'
                # chapters can be .html, .xhtml or .htm
                if result['media_type'] in ['text/html', 'application/xhtml+xml']:
                    html[path] = content
                else:
                    zfh.writestr(path, content)

            url = data.get('next')
            if url:
                time.sleep(delay)

    css = [p.removeprefix('EPUB/') for p in zfh.namelist() if p.endswith('.css')]
    for path, content in html.items():
        zfh.writestr(path, to_xhtml(content, root_path, path.removeprefix('EPUB/'), css))
    opf = next(p for p in zfh.namelist() if p.endswith('.opf'))
    zfh.writestr('META-INF/container.xml', CONTAINER.format(opf))


def main():
    parser = argparse.ArgumentParser(prog='orlydown')
    parser.add_argument('book_id', help=(
        'ID of the book, as found in its URL, '
        'e.g. 9781491958698 in https://learning.oreilly.com/library/view/…/9781491958698/'
    ))
    parser.add_argument('--jwt', metavar='TOKEN', help=(
        'Value of the orm-jwt cookie from a logged-in browser session. '
        'Without it, chapters are cut short.'
    ))
    parser.add_argument('--require-auth', action='store_true', help=(
        'Exit with an error instead of downloading truncated chapters '
        'when no JWT is given or it is not accepted.'
    ))
    parser.add_argument('--delay', type=int, default=0, help=(
        'Seconds to wait between batches of file downloads. '
        'Workaround for 403 errors caused by rate-limiting.'
    ))
    parser.add_argument('--title', action='store_true', help=(
        'Name the file after the book title instead of its ID.'
    ))
    args = parser.parse_args()

    filename = f'{args.book_id}.epub'
    get = make_getter(args.jwt)

    if args.jwt and check_auth(get):
        print('Authentication successful.')
    else:
        problem = 'Authentication failed.' if args.jwt else 'No JWT provided.'
        if args.require_auth:
            sys.exit(problem)
        print(f'{problem} Continuing without…')

    if args.title:
        data = json.loads(get(f'{BASE_URL}/api/v2/epubs/urn:orm:book:{args.book_id}/'))
        filename = data['title'].replace(':', ' -').replace('/', '-') + '.epub'

    with zipfile.ZipFile(filename, 'w') as zfh:
        fetch_book(args.book_id, zfh, get, delay=args.delay)

    print(f'created {filename}')


if __name__ == '__main__':
    main()

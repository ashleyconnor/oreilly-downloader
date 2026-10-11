# O'Reilly epub downloader

O'Reilly provides all of their books in epub format, but only through their own
reader. This script downloads the individual files and assembles them back into
a complete epub, so you can read your books in any reader (Apple Books, Calibre,
KOReader, …), e.g. for accessibility reasons.

Before using it, please read the [O'Reilly Terms of
Service](https://learning.oreilly.com/terms/).

This is a fork of [xi/oreilly-downloader](https://github.com/xi/oreilly-downloader)
that fixes epubs which didn't render properly:

-   Stylesheets are linked from every chapter, so books keep their formatting
    and fonts.
-   Images and links work in books that keep chapters in a subdirectory
    (e.g. `Text/`, `Images/`).
-   Books whose package file isn't called `content.opf` (e.g. Springer titles)
    open correctly.
-   SVG covers are scaled to fit the page instead of being cropped.
-   A `--title` option names the epub after the book instead of its ID.

## Requirements

-   Python 3.9+
-   [aiohttp](https://pypi.org/project/aiohttp/) and
    [lxml](https://pypi.org/project/lxml/)

```
pip install aiohttp lxml
```

The script declares its dependencies inline, so with
[uv](https://docs.astral.sh/uv/) you can skip the install step and use
`uv run oreilly_downloader.py …` instead of `python3 oreilly_downloader.py …`.

## Getting your JWT

Without a valid JWT every chapter is cut short. To get one:

1.  Log in to <https://learning.oreilly.com> in your browser.
2.  Open the developer tools and find the cookies for `learning.oreilly.com`.
3.  Copy the value of the `orm-jwt` cookie.

If the script reports `Authentication failed`, log in again and copy a fresh
cookie.

## Usage

Find the book ID in the book's URL, e.g. `9781491958698` in
`https://learning.oreilly.com/library/view/test-driven-development-with/9781491958698/`.

```
$ python3 oreilly_downloader.py 9781491958698 --jwt 'XYZ'
Authentication successful.
fetching https://learning.oreilly.com/api/v2/epubs/urn:orm:book:9781491958698/files/
…
created 9781491958698.epub
```

To name the file after the book instead of its ID, add `--title`:

```
$ python3 oreilly_downloader.py 9781491958698 --jwt 'XYZ' --title
…
created Test-Driven Development with Python, 2nd Edition.epub
```

A `:` in the title becomes ` -` and a `/` becomes `-`, so the name is safe to
use as a filename.

### Options

| Option        | Description                                                                   |
| ------------- | ----------------------------------------------------------------------------- |
| `--jwt TOKEN` | Your `orm-jwt` cookie. Without it, chapters are cut short.                    |
| `--title`     | Name the epub after the book title instead of its ID.                         |
| `--delay N`   | Wait `N` seconds between batches of downloads. Try `5` if you get 403 errors. |

## Similar projects

-   <https://github.com/lorenzodifuccia/safaribooks> (python)
-   <https://github.com/hurlenko/orly> (rust)
-   <https://github.com/jenni/obooks> (javascript)
-   <https://github.com/rahulvramesh/oreilly-books-grabber> (go)

## License

MIT, see [LICENSE](LICENSE).

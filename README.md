# orlydown

O'Reilly provides all of their books in epub format, but only through their own
reader. `orlydown` downloads the individual files and assembles them back into
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
-   A `--require-auth` option stops straight away if your token doesn't work.
-   No dependencies: it only uses the Python standard library.

## Installation

You need Python 3.9 or newer. The easiest way to install `orlydown` is with
[pipx](https://pipx.pypa.io/), which puts it in its own environment and adds
the `orlydown` command to your `PATH`:

```
pipx install orlydown
```

Upgrade later with `pipx upgrade orlydown`. To run it once without installing
anything:

```
pipx run orlydown 9781491958698 --jwt 'XYZ'
```

With [uv](https://docs.astral.sh/uv/), the equivalents are
`uv tool install orlydown` and `uvx orlydown …`.

Since there are no dependencies, you can also download
[`oreilly_downloader.py`](oreilly_downloader.py) and run it directly with
`python3 oreilly_downloader.py …`.

## Getting your JWT

Without a valid JWT every chapter is cut short. To get one:

1.  Log in to <https://learning.oreilly.com> in your browser.
2.  Open the developer tools and find the cookies for `learning.oreilly.com`.
3.  Copy the value of the `orm-jwt` cookie.

If `orlydown` reports `Authentication failed`, log in again and copy a fresh
cookie.

## Usage

Find the book ID in the book's URL, e.g. `9781491958698` in
`https://learning.oreilly.com/library/view/test-driven-development-with/9781491958698/`.

```
$ orlydown 9781491958698 --jwt 'XYZ'
Authentication successful.
fetching https://learning.oreilly.com/api/v2/epubs/urn:orm:book:9781491958698/files/
…
created 9781491958698.epub
```

To name the file after the book instead of its ID, add `--title`:

```
$ orlydown 9781491958698 --jwt 'XYZ' --title
…
created Test-Driven Development with Python, 2nd Edition.epub
```

A `:` in the title becomes ` -` and a `/` becomes `-`, so the name is safe to
use as a filename.

By default, a missing or rejected token only prints a warning and the download
carries on with truncated chapters. Add `--require-auth` to stop with an error
instead, which is useful in scripts:

```
$ orlydown 9781491958698 --jwt 'expired' --require-auth
Authentication failed.
$ echo $?
1
```

### Options

| Option           | Description                                                                   |
| ---------------- | ----------------------------------------------------------------------------- |
| `--jwt TOKEN`    | Your `orm-jwt` cookie. Without it, chapters are cut short.                    |
| `--require-auth` | Exit with an error if no JWT is given or it isn't accepted.                   |
| `--title`        | Name the epub after the book title instead of its ID.                         |
| `--delay N`      | Wait `N` seconds between batches of downloads. Try `5` if you get 403 errors. |

## Development

The project is managed with [uv](https://docs.astral.sh/uv/):

```
uv run orlydown --help
uv build
```

### Releasing

Pushing a `v*` tag publishes that version to PyPI. The version is the tag name
without the `v`, so `v1.0.0` publishes `1.0.0`:

```
git tag v1.0.0
git push origin v1.0.0
```

Publishing uses PyPI [trusted
publishing](https://docs.pypi.org/trusted-publishers/), so no API token is
stored in the repository. It needs a one-time setup: on PyPI, add a trusted
publisher for project `orlydown` with owner `ashleyconnor`, repository
`orlydown`, workflow `publish.yml` and environment `pypi`.

## Similar projects

-   <https://github.com/lorenzodifuccia/safaribooks> (python)
-   <https://github.com/hurlenko/orly> (rust)
-   <https://github.com/jenni/obooks> (javascript)
-   <https://github.com/rahulvramesh/oreilly-books-grabber> (go)

## License

MIT, see [LICENSE](LICENSE).

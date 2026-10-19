<div align="center">

# 📄 pdfslice-py

Split a PDF into per-page JPG images, gather them back into a PDF, or check
which pages are missing — a small, dependency-light Python library and CLI,
ported from the [pdfslice](https://github.com/DuckyMomo20012/pdfslice)
TypeScript original.

</div>

# :notebook_with_decorative_cover: Table of Contents

- [About the Project](#star2-about-the-project)
  - [Features](#dart-features)
  - [Port Notes](#books-port-notes)
- [Getting Started](#toolbox-getting-started)
  - [Prerequisites](#bangbang-prerequisites)
  - [Run Locally](#running-run-locally)
- [Usage](#eyes-usage)
  - [As a Library](#as-a-library)
  - [As a CLI](#as-a-cli)
  - [Directory Search Depth](#directory-search-depth)
  - [Flatten Output](#flatten-output)
  - [Custom Filename Template](#custom-filename-template)
  - [Output Files](#output-files)
  - [Resume and Rerun](#resume-and-rerun)
  - [Troubleshooting](#rotating_light-troubleshooting)
  - [Example Workflow](#example-workflow)
  - [End-to-End Guide](#end-to-end-guide)
- [Project Structure](#file_folder-project-structure)
- [Running Tests](#test_tube-running-tests)
- [Contributing](#wave-contributing)
- [License](#warning-license)
- [Contact](#handshake-contact)
- [Acknowledgements](#gem-acknowledgements)

## :star2: About the Project

Point it at a folder (or a single PDF); it finds every PDF, copies each one into
its own output folder, and rasterizes every page to a JPG alongside a
`.pdfslice-manifest.json` recording page hashes and the filename template used.
Run it again later to rebuild the combined PDF from those images (`gather`) or
just confirm nothing's missing (`check`) — both read the manifest, so no
page-numbering guesswork.

Standalone module: a PDF (or folder of PDFs) in, page images plus a manifest out
— and back again. No dependency on any other pipeline stage.

### :dart: Features

- Split PDF files into per-page JPG images, with the original PDF preserved and
  copied alongside the generated images.
- A `.pdfslice-manifest.json` per split unit, recording per-image SHA-256
  hashes, page count, and the filename template — the source of truth for
  `gather`/`check`.
- `check`: report missing page images without writing any PDF (read-only).
- `gather`: rebuild the combined PDF from images, skipping regeneration when
  nothing has changed since the last run, and backing up the previous PDF by
  default before overwriting it.
- Configurable output layout (`--flatten`) and page-image filename template
  (`{{filename}}`/`{{page_number}}` placeholders).
- `--dry-run` on both `split` and `gather` for safe previewing.
- Usable as a plain Python library (`split_all`/`gather_all`) or as the
  `pdfslice` CLI — same functions underneath either way.

### :books: Port Notes

Notes on how this Python port maps onto the TypeScript original:

- `pdf-to-img` + `sharp` →
  [`pypdfium2`](https://github.com/pypdfium2-team/pypdfium2)
  - [`Pillow`](https://python-pillow.org/) for rasterizing pages and encoding
    JPEGs. `pypdfium2` (Google's PDFium, BSD-licensed) was chosen over PyMuPDF
    specifically to keep pdfslice-py permissively licensed — PyMuPDF is AGPL.
- `pdf-lib` → [`pypdf`](https://pypdf.readthedocs.io/) for reading page counts,
  and Pillow's multi-page PDF writer for rebuilding a PDF from images in
  `gather`.
- `winston` → a small stdlib-`logging`-based `Logger`, with the same
  level/verbose/quiet/log-file behavior, importable on its own for library use.
- `@stricli/core` → [`click`](https://click.palletsprojects.com/) for the CLI.
- The on-disk manifest (`.pdfslice-manifest.json`) uses the exact same camelCase
  JSON schema as the TypeScript version, so a folder split by either
  implementation can be gathered/checked by the other.

## :toolbox: Getting Started

### :bangbang: Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) as package/tool manager:

```
pip install uv
```

Requires Python >= 3.10.

### :running: Run Locally

Install the CLI globally:

```bash
uv tool install .
# or, once published: uv tool install pdfslice-py
# or straight from GitHub: uv tool install git+https://github.com/DuckyMomo20012/pdfslice-py.git
```

Or clone the project and install for local development (library + CLI):

```bash
uv venv
uv pip install -e ".[test]"
uv run pdfslice --help
```

`split_all()`/`gather_all()` are plain functions you can import and call
directly, or use via the `pdfslice` CLI (see [Usage](#eyes-usage)). No network
calls either way.

## :eyes: Usage

### As a Library

```python
from pdfslice_py import split_all, gather_all

# logger is optional -- defaults to a quiet-info Logger
results = split_all("./documents")
for r in results:
    print(r.pdf, r.page_count, r.output_folder)

reports = gather_all("./documents", check_only=True)
for r in reports:
    if r.missing_pages:
        print("missing:", r.folder, r.missing_pages)
```

Pass your own `Logger` (from `pdfslice_py.create_logger`) to control verbosity,
or wire the stdlib `logging.getLogger("pdfslice_py")` into your own logging
config instead:

```python
from pdfslice_py import create_logger, split_all

logger = create_logger(verbose=True, log_file="split.log")
split_all("./documents", logger, level=2, flatten=True)
```

Everything the CLI uses is importable from the top-level package: `split_all`,
`gather_all`, `SplitResult`, `UnitReport`, `Manifest`, `read_manifest`,
`write_manifest`, `find_pdfs`, `find_images_deep`, `page_image_name`,
`parse_page_from_image_name`, `compile_template`, `DEFAULT_TEMPLATE`,
`hash_file`, `Logger`, `create_logger`.

### As a CLI

```bash
pdfslice split <input> [--level <n>] [--flatten] [--template <string>] [--dry-run] [--verbose] [--quiet] [--log-file <path>]
pdfslice gather <input> [--backup/--no-backup] [--dry-run] [--verbose] [--quiet] [--log-file <path>]
pdfslice check <input> [--verbose] [--quiet] [--log-file <path>]
```

(With `uv run`, prefix each command with `uv run`, e.g.
`uv run pdfslice split ./documents`.)

**1) Split a PDF into images**

```bash
pdfslice split ./documents
```

This scans the target folder for PDF files and creates a folder for each PDF,
for example:

```text
documents/
├── sample.pdf
└── sample/
    ├── sample.001.jpg
    ├── sample.002.jpg
    ├── sample.003.jpg
    ├── sample.pdf
    └── .pdfslice-manifest.json
```

The original PDF is preserved and copied into the generated output folder.

**2) Gather images back into a PDF**

```bash
pdfslice gather ./documents/sample
```

This rebuilds a combined PDF from the page images in the split unit folder and
**overwrites the original PDF in place** (same filename, same location). A
backup of the previous PDF (`sample.bak-<timestamp>.pdf`) is created first by
default — pass `--no-backup` to skip it. If the PDF already reflects the current
images, regeneration is skipped.

**3) Check for missing page images**

```bash
pdfslice check ./documents/sample
```

Reports missing pages without creating a PDF output. Exits with status code 1 if
any unit has missing pages.

### Directory Search Depth

```bash
pdfslice split ./documents --level 2
```

Use `--level` (or `split_all(..., level=2)`) to control how deep the search goes
when scanning nested folders.

### Flatten Output

```bash
pdfslice split ./documents --flatten
```

Places each generated output folder at the input root instead of beside each
source PDF (`flatten=True` as a library call).

### Custom Filename Template

```bash
pdfslice split ./documents --template "page-{{page_number}}.jpg"
```

Use `{{filename}}` and `{{page_number}}` placeholders to control the page image
filename (default: `{{filename}}.{{page_number}}.jpg`). Exactly one
`{{page_number}}` is required. The template is saved in the manifest, so
`gather`/`check` parse page numbers back out correctly without needing
`--template` repeated.

### Output Files

| Path | Written by | Holds |
|---|---|---|
| `<name>/<name>.pdf` | `split` | a copy of the source PDF; the original is never touched |
| `<name>/<name>.<NNN>.jpg` | `split` | one JPEG per page (2x resolution, quality 90), numbered from 1 and zero-padded to three digits |
| `<name>/.pdfslice-manifest.json` | `split`, `gather` | page count, per-image SHA-256, filename template, `updatedAt`, `gatheredAt` |
| `<name>/<name>.bak-<epoch ms>.pdf` | `gather` | the PDF as it was before it was overwritten (`--no-backup` skips it) |

### Resume and Rerun

- `split` has no skip rule: running it again rewrites every image and the manifest.
- `gather` skips a unit whose images are unchanged since the last gather
  (`No changes detected, skipping PDF creation`).
- `check` never writes anything.
- A folder counts as a split unit only if it holds a manifest.

### :rotating_light: Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Found 0 PDF(s)` | the PDFs are deeper than `--level`; raise it or pass one PDF |
| `No manifest found in unit folder` | the folder was not produced by `split`; split it, or point at the right folder |
| `Template must contain exactly one {{page_number}} placeholder` | fix `--template` |
| `gather` wrote a shorter PDF | page images were missing and `gather` does not stop for that; run `check` first, restore `<name>.bak-*.pdf` |
| two PDFs share one folder | `--flatten` with equal PDF names; rename the PDFs |

### Example Workflow

```bash
pdfslice split ./input --level 2
pdfslice check ./input/report
pdfslice gather ./input/report
```

### End-to-End Guide

Install, split, check, sort the images for the OCR pipeline, rebuild a PDF, and the common problems:
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

## :file_folder: Project Structure

```text
src/pdfslice_py/
├── __init__.py             # public library API (re-exports below)
├── cli.py                  # click CLI: split, gather, check commands
├── discover.py             # find_pdfs, find_images_deep, page_image_name
├── filename_template.py    # {{filename}}/{{page_number}} template compiler
├── gather.py                # rebuild PDF from images / check-only mode
├── hash.py                  # streamed SHA-256 file hashing
├── logger.py                 # verbose/quiet/log-file logger
├── manifest.py                # .pdfslice-manifest.json schema + read/write
└── split.py                   # PDF -> per-page JPG splitting
tests/
├── test_cli.py
├── test_discover.py
├── test_filename_template.py
├── test_manifest.py
└── test_split_gather.py
docs/
├── SPECIFICATION.md         # what the code does today
└── USER_GUIDE.md            # end-to-end guide
```

## :test_tube: Running Tests

```bash
uv sync
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

## :wave: Contributing

Contributions are always welcome!

Please read the [contribution guidelines](./CONTRIBUTING.md).

Repo-specific rules: the manifest keeps the camelCase JSON schema of the TypeScript original, so
folders split by either tool stay readable by the other; the library never calls the network and does not depend
on any pipeline repo.

<!-- Code of Conduct -->

### :scroll: Code of Conduct

Please read the [Code of Conduct](./CODE_OF_CONDUCT.md).

## :warning: License

This project is licensed under the **Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**
License, matching the
[TypeScript original](https://github.com/DuckyMomo20012/pdfslice).

[![License: CC BY-NC-SA 4.0](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/4.0/).

See the **[LICENSE.md](./LICENSE.md)** file for full details.

<!-- Contact -->

## :handshake: Contact

Duong Vinh - [@duckymomo20012](https://twitter.com/duckymomo20012) -
tienvinh.duong4@gmail.com

## :gem: Acknowledgements

- [pdfslice](https://github.com/DuckyMomo20012/pdfslice) — the TypeScript
  original this project ports.
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) — PDF page
  rasterization (Google's PDFium, BSD-licensed).
- [Pillow](https://python-pillow.org/) — JPEG encoding and multi-page PDF
  assembly.
- [pypdf](https://pypdf.readthedocs.io/) — PDF page counting.
- [click](https://click.palletsprojects.com/) — the CLI framework.
- [uv](https://docs.astral.sh/uv/) — Python packaging and tool management.

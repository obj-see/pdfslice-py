# pdfslice-py: User Guide

From a scanned book PDF to a folder of page images that the OCR pipeline can
read, and back again if you ever need the PDF rebuilt from edited images. The
README lists every option; this guide is the order in which to do things and
the checks after each step. Every command below was run against a small test
PDF while writing it.

## 1. What you will have at the end

For `documents/sample.pdf` (3 pages):

```text
documents/
├── sample.pdf                    the original, never touched by split
└── sample/
    ├── sample.pdf                a copy of the original
    ├── sample.001.jpg            one JPEG per page, 2x resolution, quality 90
    ├── sample.002.jpg
    ├── sample.003.jpg
    └── .pdfslice-manifest.json   page count, SHA-256 of every file, name template
```

The manifest is how `check` and `gather` know what a complete unit is. Do not
delete it.

## 2. Install

```bash
pip install uv
uv tool install git+https://github.com/DuckyMomo20012/pdfslice-py.git   # the CLI everywhere
pdfslice --version
```

Or from a clone, for development:

```bash
git clone https://github.com/DuckyMomo20012/pdfslice-py.git
cd pdfslice-py
uv sync
uv run pdfslice --help
```

Python 3.10 or newer. No network access is needed to run it, and nothing is
sent anywhere.

## 3. Prepare the PDFs

- One folder holding the PDFs of one batch, for example `scans/`.
- The PDF file name (without `.pdf`) becomes the output folder name and the
  start of every image name, so name the files the way you want the images
  named: `book-001.pdf`, not `scan (3) final.pdf`.
- Two PDFs with the same name in different folders must not be split with
  `--flatten`: they would share one output folder.

## 4. Split

Preview first. A dry run writes nothing and shows the folder, the copy and
every image name:

```bash
pdfslice split scans --dry-run
pdfslice split scans                 # PDFs directly in scans/
pdfslice split scans --level 2       # also PDFs one subfolder deeper
pdfslice split scans/book-001.pdf    # one file
```

Check, per PDF:

1. The log ends with `Done. Processed N PDF(s).` and N is the number you
   expect (`--level` too low is the usual reason for fewer).
2. Open the first, a middle and the last JPEG. Pages should be upright and
   readable; the image has twice the PDF's native resolution.
3. The number of JPEGs equals the PDF's page count (it is also stored as
   `pageCount` in the manifest).

Running `split` again on the same PDF rewrites every image and the manifest;
there is no skip rule. Do it before you sort or edit the images, not after.

### Options

| Option | Use |
|---|---|
| `-l`, `--level N` | how many folder levels to search for PDFs (`1` = only directly in the folder) |
| `-f`, `--flatten` | put every output folder directly under the input folder instead of beside each PDF |
| `--template T` | image name pattern, default `{{filename}}.{{page_number}}.jpg`; exactly one `{{page_number}}` is required, an invalid template stops with a `ValueError` |
| `--dry-run` | preview only |
| `--verbose`, `--quiet`, `--log-file PATH` | debug lines, errors only, and a JSON-lines copy of the log |

Page numbers are zero-padded to three digits below 1000 (`001`, `012`, `1000`),
so a plain alphabetical sort is also the page order. Keep the default template
for pipeline work.

## 5. Check

```bash
pdfslice check scans
```

Read-only. It finds every unit (a folder with a manifest) at any depth below
`scans`, compares the pages of the PDF with the images found, and exits with
status 1 if any unit has a missing page, naming the pages
(`missing_pages: [2]`). Use it in a script or before any other step:

```bash
pdfslice check scans && echo "all pages present"
```

## 6. Hand the images to the OCR pipeline

The pipeline reads **unit folders that directly hold page images**. A book
normally has one unit per script, under the same parent, named `ch` (Sino-Nom
pages), `vi` (Vietnamese pages), plus `blank` and `intro` for pages that no
stage should process:

```text
books/T1/book-001/images/ch/   book-001.001.jpg ... book-001.120.jpg
books/T1/book-001/images/vi/   book-001.121.jpg ... book-001.240.jpg
books/T1/book-001/images/intro/  cover and front matter
books/T1/book-001/images/blank/  empty pages
```

Sort by hand: look at the images, then move only the JPEGs into those
folders, leaving the PDF copy and the manifest behind in the split folder
(they are not pipeline input). In bash, for pages 1 to 120 as Sino-Nom:

```bash
mkdir -p books/T1/book-001/images/{ch,vi,intro,blank}
mv scans/book-001/book-001.{001..120}.jpg books/T1/book-001/images/ch/
mv scans/book-001/book-001.{121..240}.jpg books/T1/book-001/images/vi/
```

Keep the file names: the page number in the name is the page identity for
every later stage. Do not rename, renumber or convert the images. Then
continue with `ocr-engines` (see the user guide of `ocr-pipeline`, step 1).
`books/` is the `--input-dir` of the engine stage.

Moving images out of the split folder breaks `pdfslice check` and `gather` for
that folder (the pages are no longer there). If you may need to rebuild the
PDF, **copy** instead of move (`cp`), or keep the split folder as the archive.

## 7. Rebuild a PDF from images (optional)

Use this when you fixed or replaced page images (rotated, cropped, rescanned)
and want the PDF to match:

```bash
pdfslice check scans/book-001          # 1: every page must be present
pdfslice gather scans/book-001 --dry-run   # 2: preview
pdfslice gather scans/book-001         # 3: do it
```

`gather` writes a multi-page PDF from the images (one pixel per PDF point) and
**overwrites the PDF in the split folder** (`scans/book-001/book-001.pdf`, the
copy; your original next to the folder is not touched). Before overwriting it
copies the current PDF to `book-001.bak-<epoch milliseconds>.pdf`; `--no-backup`
turns that off. If nothing changed since the last gather, it prints
`No changes detected, skipping PDF creation`.

**Read this before using `gather`.** A missing page image does not stop it: it
logs a warning, then writes a shorter PDF from the images that exist and exits
with status 0. After that, `check` reads the shorter PDF and calls the unit
complete. So always run `check` first, and if you see a short PDF by mistake,
restore it from the `.bak-*.pdf` file. A unit with no images at all fails with
an `IndexError`.

## 8. From Python

```python
from pdfslice_py import split_all, gather_all, create_logger

logger = create_logger(verbose=True, log_file="split.log")
for r in split_all("scans", logger, level=2):
    print(r.pdf, r.page_count, r.output_folder)

for u in gather_all("scans", check_only=True):
    if u.missing_pages:
        print("missing:", u.folder, u.missing_pages)
```

Everything the CLI uses is importable from the top-level package; the list is
in the README.

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Found 0 PDF(s)` | the PDFs are deeper than `--level`; raise it, or pass one PDF |
| `check` says `missing-source` or `No manifest found` | the folder has no manifest, so it is not a split unit; split it, or point at the right folder |
| `Template must contain exactly one {{page_number}} placeholder` | fix `--template` |
| blurry pages | the scan is low resolution; split renders at 2x of the PDF's native size and cannot add detail |
| two PDFs share one folder | you used `--flatten` with equal PDF names; rename the PDFs |
| `gather` produced a shorter PDF | pages were missing; restore `<name>.bak-*.pdf` |
| `pdfslice --version` shows an old number | you run an old install; reinstall |

## 10. Quick reference

```bash
pdfslice split  scans --level 2 [--flatten] [--template T] [--dry-run]
pdfslice check  scans                          # exit 1 if a page is missing
pdfslice gather scans/book-001 [--no-backup] [--dry-run]
```

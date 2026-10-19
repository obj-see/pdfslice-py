# pdfslice-py specification

Status: v1.1.0, 2026-10-18. Describes what the code does today: splitting PDFs into per-page JPEGs, a per-unit manifest, gathering images back into a PDF, and a read-only check. Pipeline: `PIPELINE.md` v0.10 §3.0.
Evidence labels: **[you]** confirmed by the user, **[code]** read or run in this repo, **[run]** executed in a build session, **[user]** needs the user, **[proposal]** a design not yet confirmed, **[open]** not decided.

## 1. Purpose

Turn a PDF into one JPEG per page, remember what was produced, and rebuild or verify the PDF later. It is the first step of the OCR pipeline (page images for `ocr-engines` and `ocr-layout`) and is also a stand-alone library and CLI. It is a Python port of the TypeScript tool `pdfslice`; the manifest JSON schema is the same, so a folder split by either tool can be gathered or checked by the other.

## 2. Position in the pipeline

```text
PDF ──pdfslice split──▶ <name>/<name>.001.jpg ...   (this repo)
                         │  sorted by hand into unit folders (ch, vi, blank, intro)
                         ▼
                      ocr-engines, ocr-layout, ...
```

No dependency on `ocr-flow` or any other pipeline repo; no network calls. The hand-over rules are in `docs/USER_GUIDE.md`.

## 3. Repo layout

```text
src/pdfslice_py/
├── __init__.py            public API (everything below is re-exported)
├── cli.py                 click group `pdfslice`: split, gather, check
├── discover.py            find_pdfs, find_images_deep, page_image_name, parse_page_from_image_name
├── filename_template.py   {{filename}} / {{page_number}} template: render and parse
├── gather.py              gather_all, UnitReport, check-only mode
├── hash.py                hash_file (streamed SHA-256)
├── logger.py              Logger, create_logger
├── manifest.py            Manifest, read_manifest, write_manifest
└── split.py               split_all, SplitResult
tests/                     synthetic PDFs built with Pillow
```

Dependencies: `click`, `pypdf` (page counts), `pypdfium2` (rasterizing), `pillow` (JPEG and PDF writing). Python >= 3.10.

## 4. Split

`split_all(input, logger=None, level=1, flatten=False, template=DEFAULT_TEMPLATE, dry_run=False) -> list[SplitResult]`

1. `find_pdfs(input, level)`: `input` may be one PDF file or a folder. With a folder, `level=1` finds PDFs directly in it, `level=2` one subfolder deeper, and so on. Extension match is case-insensitive.
2. For each PDF, the output folder is `<stem>` placed beside the PDF, or directly under `input` with `flatten=True`. A flattened name collision is not detected: two PDFs with the same stem share one folder.
3. The PDF is **copied** into the output folder (the original is never moved or deleted); an existing copy is not overwritten.
4. Every page is rasterized by PDFium at scale 2 and saved as JPEG quality 90 (RGB). Existing images with the same name are overwritten: `split` has no skip-if-done rule.
5. File names come from the template (section 6). A SHA-256 is recorded per image.
6. `.pdfslice-manifest.json` is written last (section 5).

`dry_run=True` logs what would be done, writes nothing and returns `SplitResult(skipped=True, images=[])` with the page count read by `pypdf`.

`SplitResult(pdf, output_folder, page_count, images, skipped)`: `pdf` is the path of the copy inside the output folder (the source path in a dry run).

## 5. Manifest

`<unit>/.pdfslice-manifest.json`, camelCase keys, 2-space indent:

| Key | Meaning |
|---|---|
| `version` | schema version, `1` |
| `sourcePdf` | file name of the PDF inside the unit folder |
| `sourcePdfHash` | SHA-256 of that PDF |
| `pageCount` | pages of the PDF when the manifest was written |
| `images` | `[{file, page, hash}]` in page order; `file` is relative to the unit folder |
| `updatedAt` | UTC ISO time of the last write |
| `gatheredAt` | UTC ISO time of the last `gather` that wrote a PDF, else `null` |
| `filenameTemplate` | the template used; empty means the default |

A unit folder is recognized **by the manifest**, not by a PDF in it. `gather` and `check` do not descend into a recognized unit.

## 6. Filename template

Default `{{filename}}.{{page_number}}.jpg`. `{{filename}}` is the PDF stem. Exactly one `{{page_number}}` is required, otherwise `ValueError`. The page number is zero-padded to 3 digits below 1000 and unpadded from 1000. Parsing back uses a case-insensitive regex built from the template: `{{filename}}` matches any text, `{{page_number}}` matches digits. The template is stored in the manifest, so `gather` and `check` need no `--template`.

## 7. Gather and check

`gather_all(input, logger=None, dry_run=False, check_only=False, backup=True) -> list[UnitReport]`

For every unit folder (a folder with a manifest) under `input`, searched at any depth:

1. No manifest or no source PDF: warning, action `missing-source`.
2. Page count is read from the source PDF **as it is now**. Images are collected at any depth below the unit (`.jpg`, `.jpeg`); a name that does not parse with the template is ignored.
3. `missing_pages` = pages `1..page_count` with no image. A warning lists them.
4. `check_only=True` stops here (action `check-only`, nothing written).
5. If the manifest has `gatheredAt`, the same page count, and the same image hashes in the same order, and nothing is missing: action `skipped-unchanged`.
6. `dry_run=True`: action `would-create`.
7. Otherwise: with `backup=True` the current PDF is copied to `<stem>.bak-<epoch ms>.pdf`; the images found, in page order, are written as a multi-page PDF (one pixel per point, 72 DPI) **over the source PDF**; the manifest is rewritten with the current images, new `sourcePdfHash`, `updatedAt` and `gatheredAt`. Action `created`.

`UnitReport(folder, source_pdf, page_count, found_images, missing_pages, action, output_pdf)`, action one of `created`, `skipped-unchanged`, `would-create`, `missing-source`, `check-only`.

What happens when a page image is missing is listed under Open: a missing page does not stop `gather`.

## 8. Logging

`create_logger(verbose=False, quiet=False, log_file=None)`: level `info` by default, `debug` with `verbose`, `error` only with `quiet`. Each record can carry key-value metadata and, with `log_file`, is appended as one JSON line. Library calls without a logger use a quiet-info logger. The stdlib logger `pdfslice_py` is not used.

## 9. CLI and release

```text
pdfslice split  INPUT [-l/--level N] [-f/--flatten] [--template T] [--dry-run] [--verbose] [--quiet] [--log-file PATH]
pdfslice gather INPUT [--backup/--no-backup] [--dry-run] [--verbose] [--quiet] [--log-file PATH]
pdfslice check  INPUT [--verbose] [--quiet] [--log-file PATH]
pdfslice --version
```

Exit codes: `check` exits 1 when any unit has missing pages, else 0. `split` and `gather` exit 0 even when pages are missing; an invalid template raises `ValueError` (non-zero exit with a traceback). Output: log lines on stdout, `error` lines on stderr.

**Release.** Conventional commits on `main`: `release-please` opens the release PR, updates `CHANGELOG.md` and the version in `pyproject.toml`, and a release publishes to PyPI. `pdfslice --version` prints `pdfslice_py.__version__`; keep it equal to the version in `pyproject.toml`.

## 10. Tests

`tests/` needs no network and no fixture files: discovery and depth, template render and parse (padding, dots in names, case, errors), manifest round trip and camelCase keys, one split then gather then check round trip on a PDF built with Pillow, `check` reporting a missing page, and the CLI version string. The behaviors listed under Open (section 13) have no test on purpose.

## 11. Acceptance

A fresh clone passes `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -v`, and the round trip works by hand on a small PDF: `pdfslice split`, `pdfslice check` (exit 0), delete one image, `pdfslice check` (exit 1 and the page named), restore it, `pdfslice gather` (backup written, then `skipped-unchanged` on the second run). **[run]** the round trip and the exit codes were run in a build session on a generated 3-page PDF; `ruff` **[not run]**.

## 12. Non-goals

OCR, image processing beyond JPEG encoding, PDF text extraction, a GUI, any pipeline orchestration (that is `ocr-flow`).

## 13. Open

- **[open] `gather` with missing pages.** It still overwrites the PDF with a shorter one built from the images that exist (after the backup) and exits 0; the next `check` then reports the unit complete. Proposal: refuse to overwrite when pages are missing unless `--allow-missing` is given, and exit 1. Not changed yet.
- **[open] `gather` with no images.** A unit with no images and missing pages raises `IndexError`.
- **[open]** Two images with the same page number (for example one in a subfolder) are both written, in discovery order.
- **[open]** `--flatten` does not detect two PDFs with the same stem; they share one output folder.

from pathlib import Path

from pypdf import PdfWriter

from pdfslice_py.gather import gather_all
from pdfslice_py.logger import create_logger
from pdfslice_py.manifest import read_manifest
from pdfslice_py.split import split_all


def _make_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def test_split_then_gather_round_trip(tmp_path: Path):
    logger = create_logger(quiet=True)
    src = tmp_path / "sample.pdf"
    _make_pdf(src, pages=2)

    results = split_all(tmp_path, logger)
    assert len(results) == 1
    assert results[0].page_count == 2
    assert results[0].skipped is False

    unit_folder = tmp_path / "sample"
    assert unit_folder.is_dir()
    assert (unit_folder / "sample.001.jpg").exists()
    assert (unit_folder / "sample.002.jpg").exists()

    manifest = read_manifest(unit_folder)
    assert manifest is not None
    assert manifest.pageCount == 2
    assert manifest.gatheredAt is None

    reports = gather_all(tmp_path, logger, check_only=True)
    assert len(reports) == 1
    assert reports[0].missing_pages == []
    assert reports[0].action == "check-only"

    gathered = gather_all(tmp_path, logger, backup=False)
    assert gathered[0].action == "created"
    assert (unit_folder / "sample.pdf").exists()

    manifest_after = read_manifest(unit_folder)
    assert manifest_after is not None
    assert manifest_after.gatheredAt is not None

    # second gather with nothing changed should skip regeneration
    gathered_again = gather_all(tmp_path, logger, backup=False)
    assert gathered_again[0].action == "skipped-unchanged"


def test_check_reports_missing_pages(tmp_path: Path):
    logger = create_logger(quiet=True)
    src = tmp_path / "sample.pdf"
    _make_pdf(src, pages=2)
    split_all(tmp_path, logger)

    unit_folder = tmp_path / "sample"
    (unit_folder / "sample.002.jpg").unlink()

    reports = gather_all(tmp_path, logger, check_only=True)
    assert reports[0].missing_pages == [2]


def test_broken_pdf_does_not_abort_the_run_and_reports_where(tmp_path: Path, capsys):
    (tmp_path / "a-broken.pdf").write_bytes(b"not a pdf")
    _make_pdf(tmp_path / "b-good.pdf", pages=2)

    results = split_all(tmp_path, create_logger())

    assert [Path(r.pdf).name for r in results] == ["a-broken.pdf", "b-good.pdf"]
    assert results[0].failed is True
    assert results[0].error_message is not None
    assert results[1].failed is False
    assert results[1].page_count == 2
    # no manifest for the failed pdf: gather/check treat it as not split
    assert not (tmp_path / "a-broken" / ".pdfslice-manifest.json").exists()
    err = capsys.readouterr().err
    assert "Failed to split PDF" in err
    assert '"stage":"open"' in err


def test_pdfs_are_processed_in_sorted_order(tmp_path: Path):
    _make_pdf(tmp_path / "b.pdf", pages=1)
    _make_pdf(tmp_path / "a.pdf", pages=1)

    results = split_all(tmp_path, create_logger(quiet=True))

    assert [Path(r.pdf).name for r in results] == ["a.pdf", "b.pdf"]


def test_gather_skips_unit_with_no_images_instead_of_overwriting_pdf(tmp_path: Path):
    logger = create_logger(quiet=True)
    _make_pdf(tmp_path / "sample.pdf", pages=2)
    split_all(tmp_path, logger)
    unit = tmp_path / "sample"
    for jpg in unit.glob("*.jpg"):
        jpg.unlink()
    before = (unit / "sample.pdf").read_bytes()

    reports = gather_all(tmp_path, logger, backup=False)

    assert reports[0].action == "no-images"
    assert (unit / "sample.pdf").read_bytes() == before


def test_partial_gather_keeps_reporting_the_missing_page(tmp_path: Path):
    logger = create_logger(quiet=True)
    _make_pdf(tmp_path / "sample.pdf", pages=3)
    split_all(tmp_path, logger)
    (tmp_path / "sample" / "sample.002.jpg").unlink()

    first = gather_all(tmp_path, logger, backup=False)
    second = gather_all(tmp_path, logger, backup=False)

    # the overwritten pdf has 2 pages, but the expected count stays 3
    assert first[0].missing_pages == [2]
    assert second[0].missing_pages == [2]


def test_unchanged_pdf_is_skipped_unless_forced(tmp_path: Path):
    logger = create_logger(quiet=True)
    _make_pdf(tmp_path / "sample.pdf", pages=2)

    first = split_all(tmp_path, logger)
    second = split_all(tmp_path, logger)
    third = split_all(tmp_path, logger, force=True)

    assert first[0].skipped is False
    assert second[0].skipped is True
    assert second[0].page_count == 2
    assert third[0].skipped is False


def test_resplit_clears_stale_images(tmp_path: Path):
    logger = create_logger(quiet=True)
    _make_pdf(tmp_path / "sample.pdf", pages=3)
    split_all(tmp_path, logger)
    stale = tmp_path / "sample" / "sample.009.jpg"
    stale.write_bytes(b"stale")

    split_all(tmp_path, logger, force=True)

    assert not stale.exists()


def test_progress_and_outcome_are_logged(tmp_path: Path, capsys):
    _make_pdf(tmp_path / "a.pdf", pages=1)
    _make_pdf(tmp_path / "b.pdf", pages=2)

    split_all(tmp_path, create_logger())

    out = capsys.readouterr().out
    assert "Processing PDF 1/2" in out
    assert "Processing PDF 2/2" in out
    assert "Split complete: 2 page(s)" in out

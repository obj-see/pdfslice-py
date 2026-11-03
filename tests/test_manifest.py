from pathlib import Path

from pdfslice_py.manifest import (
    MANIFEST_FILENAME,
    Manifest,
    ManifestImageEntry,
    manifest_path_for,
    read_manifest,
    write_manifest,
)


def test_manifest_path_for(tmp_path: Path):
    assert manifest_path_for(tmp_path) == tmp_path / MANIFEST_FILENAME


def test_read_manifest_returns_none_when_absent(tmp_path: Path):
    assert read_manifest(tmp_path) is None


def test_write_then_read_round_trips(tmp_path: Path):
    manifest = Manifest(
        version=1,
        sourcePdf="sample.pdf",
        sourcePdfHash="deadbeef",
        pageCount=2,
        images=[
            ManifestImageEntry(file="sample.001.jpg", page=1, hash="aaa"),
            ManifestImageEntry(file="sample.002.jpg", page=2, hash="bbb"),
        ],
        updatedAt="2026-01-01T00:00:00+00:00",
        filenameTemplate="{{filename}}.{{page_number}}.jpg",
    )
    write_manifest(tmp_path, manifest)

    loaded = read_manifest(tmp_path)
    assert loaded is not None
    assert loaded.sourcePdf == "sample.pdf"
    assert loaded.pageCount == 2
    assert loaded.gatheredAt is None
    assert [i.file for i in loaded.images] == ["sample.001.jpg", "sample.002.jpg"]


def test_json_schema_uses_camel_case_keys(tmp_path: Path):
    manifest = Manifest(
        version=1,
        sourcePdf="a.pdf",
        sourcePdfHash="h",
        pageCount=0,
        updatedAt="now",
        filenameTemplate="{{filename}}.{{page_number}}.jpg",
    )
    write_manifest(tmp_path, manifest)
    raw = manifest_path_for(tmp_path).read_text()
    for key in ("sourcePdf", "sourcePdfHash", "pageCount", "updatedAt", "filenameTemplate"):
        assert f'"{key}"' in raw


def test_manifest_written_like_the_ts_cli(tmp_path: Path):
    manifest = Manifest(
        version=1,
        sourcePdf="Sách Dạy (Quyển 11).pdf",
        sourcePdfHash="h",
        pageCount=0,
        updatedAt="2026-01-01T00:00:00.000Z",
        filenameTemplate="{{filename}}.{{page_number}}.jpg",
    )
    write_manifest(tmp_path, manifest)
    raw = manifest_path_for(tmp_path).read_text(encoding="utf-8")
    assert "Sách Dạy (Quyển 11).pdf" in raw  # raw UTF-8, not \u escapes
    assert "gatheredAt" not in raw  # omitted until the first gather


def test_reads_manifest_written_by_the_ts_cli(tmp_path: Path):
    manifest_path_for(tmp_path).write_text(
        '{"version":1,"sourcePdf":"a.pdf","sourcePdfHash":"h","pageCount":1,'
        '"images":[{"file":"a.001.jpg","page":1,"hash":"x"}],'
        '"updatedAt":"2026-01-01T00:00:00.000Z","filenameTemplate":"{{filename}}.{{page_number}}.jpg"}',
        encoding="utf-8",
    )
    loaded = read_manifest(tmp_path)
    assert loaded is not None
    assert loaded.gatheredAt is None
    assert loaded.images[0].page == 1

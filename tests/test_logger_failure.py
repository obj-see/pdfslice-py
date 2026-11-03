import json
from pathlib import Path

from pdfslice_py.failure import describe_error, get_progress, set_progress
from pdfslice_py.logger import create_logger, format_line


def test_format_line_matches_ts_cli():
    assert format_line("info", "hi", {"output_folder": "x"}) == (
        '\033[32minfo\033[39m: hi {"outputFolder":"x"}'
    )
    assert format_line("error", "bad") == "\033[31merror\033[39m: bad"


def test_format_line_keeps_utf8_and_drops_none_and_reserved_keys():
    line = format_line("info", "m", {"name": "Sách", "page": None, "level": 1})
    assert line.endswith('m {"name":"Sách"}')


def test_log_file_is_one_compact_json_object_per_line(tmp_path: Path, capsys):
    log_file = tmp_path / "log.jsonl"
    logger = create_logger(log_file=log_file)
    logger.info("Processing", pdf_path="Sách.pdf", page=None)
    record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
    assert record["level"] == "info"
    assert record["pdfPath"] == "Sách.pdf"
    assert "page" not in record
    assert record["timestamp"].endswith("Z")


def test_errors_go_to_stderr(capsys):
    create_logger().error("boom")
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert captured.out == ""


def test_describe_error_has_name_message_stack_code_and_cause():
    try:
        try:
            Path("/definitely/not/here").read_text()
        except OSError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as err:
        detail = describe_error(err)
    assert detail["name"] == "RuntimeError"
    assert "outer" in detail["stack"]
    assert detail["cause"]["code"] == "ENOENT"


def test_progress_is_a_copy():
    set_progress(pdf_path="a.pdf", stage="render", page=4)
    progress = get_progress()
    assert progress == {"pdf_path": "a.pdf", "stage": "render", "page": 4}
    progress["page"] = 99
    assert get_progress()["page"] == 4

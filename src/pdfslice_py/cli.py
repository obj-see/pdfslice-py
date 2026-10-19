"""CLI: split, gather, check commands."""

from __future__ import annotations

import sys

import click

from . import __version__
from .filename_template import DEFAULT_TEMPLATE
from .gather import gather_all
from .logger import create_logger
from .split import split_all


def _log_flags(f: click.decorators.FC) -> click.decorators.FC:
    f = click.option("--verbose", is_flag=True, default=False, help="Enable debug logging")(f)
    f = click.option("--quiet", is_flag=True, default=False, help="Only log errors")(f)
    f = click.option("--log-file", default=None, help="Path to also write logs as JSON")(f)
    return f


@click.group()
@click.version_option(version=__version__, prog_name="pdfslice")
def cli() -> None:
    """Split PDFs into page images, then gather or check them back."""


@cli.command("split")
@click.argument("input", type=str)
@click.option(
    "-l",
    "--level",
    type=int,
    default=1,
    help="How many directory levels deep to search for PDFs",
)
@click.option(
    "-f",
    "--flatten",
    is_flag=True,
    default=False,
    help="Pull every discovered PDF's output folder to the input root, "
    "instead of alongside each PDF",
)
@click.option(
    "--template",
    type=str,
    default=DEFAULT_TEMPLATE,
    help="Page image filename template. Placeholders: {{filename}}, "
    "{{page_number}}. Must contain exactly one {{page_number}}.",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Preview actions without writing any files"
)
@_log_flags
def split_cmd(
    input: str,  # noqa: A002 - mirrors Click argument name and TS API
    level: int,
    flatten: bool,
    template: str,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
    log_file: str | None,
) -> None:
    """Split PDF(s) into per-page JPG images alongside the source file."""
    logger = create_logger(verbose=verbose, quiet=quiet, log_file=log_file)
    results = split_all(
        input,
        logger,
        level=level,
        flatten=flatten,
        template=template,
        dry_run=dry_run,
    )
    logger.info(f"Done. Processed {len(results)} PDF(s).")


@cli.command("gather")
@click.argument("input", type=str)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Preview actions without writing any files"
)
@click.option(
    "--backup/--no-backup",
    default=True,
    help="Back up the existing PDF before overwriting it",
)
@_log_flags
def gather_cmd(
    input: str,  # noqa: A002 - mirrors Click argument name and TS API
    dry_run: bool,
    backup: bool,
    verbose: bool,
    quiet: bool,
    log_file: str | None,
) -> None:
    """Gather page images back into a PDF, reporting any missing pages."""
    logger = create_logger(verbose=verbose, quiet=quiet, log_file=log_file)
    reports = gather_all(input, logger, dry_run=dry_run, check_only=False, backup=backup)

    with_missing = [r for r in reports if r.missing_pages]
    if with_missing:
        logger.warn(f"{len(with_missing)} unit(s) have missing pages")
    logger.info(f"Done. Processed {len(reports)} unit folder(s).")


@cli.command("check")
@click.argument("input", type=str)
@_log_flags
def check_cmd(
    input: str,  # noqa: A002 - mirrors Click argument name and TS API
    verbose: bool,
    quiet: bool,
    log_file: str | None,
) -> None:
    """Report missing page images without writing any PDF (read-only)."""
    logger = create_logger(verbose=verbose, quiet=quiet, log_file=log_file)
    reports = gather_all(input, logger, check_only=True)

    with_missing = [r for r in reports if r.missing_pages]
    if with_missing:
        logger.warn(f"{len(with_missing)} unit(s) have missing pages")
        sys.exit(1)
    else:
        logger.info(f"All {len(reports)} unit(s) complete.")


if __name__ == "__main__":
    cli()

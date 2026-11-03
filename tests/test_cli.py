from click.testing import CliRunner

from pdfslice_py import __version__
from pdfslice_py.cli import cli


def test_version_option_prints_the_package_version():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output

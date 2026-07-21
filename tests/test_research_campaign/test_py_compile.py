import glob
import py_compile
from pathlib import Path

# Anchored on this file's location (not cwd) so this test is correct
# regardless of the directory pytest is invoked from.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_research_campaign_source_compiles() -> None:
    files = glob.glob(str(_REPO_ROOT / "src" / "hunter" / "research_campaign" / "*.py"))
    assert files, "no source files found"
    for f in files:
        py_compile.compile(f, doraise=True)


def test_research_campaign_tests_compile() -> None:
    files = glob.glob(str(_REPO_ROOT / "tests" / "test_research_campaign" / "*.py"))
    assert files, "no test files found"
    for f in files:
        py_compile.compile(f, doraise=True)

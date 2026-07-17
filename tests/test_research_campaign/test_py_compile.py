import py_compile
import glob


def test_research_campaign_source_compiles() -> None:
    files = glob.glob("src/hunter/research_campaign/*.py")
    assert files, "no source files found"
    for f in files:
        py_compile.compile(f, doraise=True)


def test_research_campaign_tests_compile() -> None:
    files = glob.glob("tests/test_research_campaign/*.py")
    assert files, "no test files found"
    for f in files:
        py_compile.compile(f, doraise=True)

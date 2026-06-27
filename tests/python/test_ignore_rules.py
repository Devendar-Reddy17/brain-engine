from brain.core.repo.ignore_rules import (
    detect_language,
    is_ignored_dir,
    is_supported_file,
    path_has_ignored_component,
)


def test_ignored_dirs():
    for d in ("node_modules", "target", "build", "dist", ".git", ".idea", ".vscode", "coverage", ".tmp"):
        assert is_ignored_dir(d)
    assert not is_ignored_dir("src")


def test_detect_language():
    assert detect_language("Main.java") == "java"
    assert detect_language("app.py") == "python"
    assert detect_language("pom.xml") == "xml"
    assert detect_language("application.properties") == "properties"
    assert detect_language("README.unknownext") is None


def test_is_supported_file():
    assert is_supported_file("Service.java")
    assert is_supported_file("application.yml")
    assert not is_supported_file("image.png")


def test_path_has_ignored_component():
    assert path_has_ignored_component(("project", "node_modules", "x.js"))
    assert path_has_ignored_component(("a", "target", "Main.class"))
    assert not path_has_ignored_component(("src", "main", "java", "App.java"))

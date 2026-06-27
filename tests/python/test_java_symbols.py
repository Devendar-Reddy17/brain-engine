"""Tests for Java symbol extraction.

Uses the regex FallbackJavaParser directly so the tests do not require the
native tree-sitter grammar to be installed.
"""

from brain.core.parsing.fallback_java_parser import FallbackJavaParser

SAMPLE = """
package com.example.auth;

import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PostMapping;

@RestController
@RequestMapping("/auth")
public class LoginController {

    @Autowired
    private LoginService loginService;

    @PostMapping("/login")
    public String login(LoginRequest request) {
        return loginService.authenticate(request);
    }

    @Test
    public void testLogin() {
        login(null);
    }
}
"""


def _parse():
    return FallbackJavaParser().parse(SAMPLE, "LoginController.java")


def test_package_detected():
    result = _parse()
    assert result.package == "com.example.auth"


def test_imports_detected():
    result = _parse()
    assert "org.springframework.web.bind.annotation.RestController" in result.imports


def test_class_and_annotations():
    result = _parse()
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "LoginController" for c in classes)
    controller = next(c for c in classes if c.name == "LoginController")
    assert "RestController" in controller.annotations


def test_route_handler_detected():
    result = _parse()
    routes = [s for s in result.symbols if s.kind == "route"]
    assert any(r.name == "login" for r in routes)
    login = next(r for r in routes if r.name == "login")
    assert login.route is not None and "POST" in login.route


def test_test_method_detected():
    result = _parse()
    tests = [s for s in result.symbols if s.is_test]
    assert any(t.name == "testLogin" for t in tests)

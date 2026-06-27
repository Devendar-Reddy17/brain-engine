const test = require("node:test");
const assert = require("node:assert");

const { formatExecutionPath, formatLocalResult } = require("../dist/commands/askFormat");

test("formats execution path labels", () => {
  assert.strictEqual(formatExecutionPath("local"), "Local Repository Query");
  assert.strictEqual(formatExecutionPath("ai_required"), "AI Reasoning");
});

test("renders a local result with count and navigable items", () => {
  const result = {
    queryType: "tag:controller",
    title: "Controllers",
    count: 2,
    items: [
      { name: "AuthController", kind: "class", filePath: "src/AuthController.java", startLine: 10, endLine: 40 },
      { name: "UserController", kind: "class", filePath: "src/UserController.java", startLine: 5, endLine: 60 },
    ],
    staleWarning: null,
  };
  const lines = formatLocalResult(result);
  assert.strictEqual(lines[0], "Controllers: 2");
  assert.ok(lines.includes("- AuthController (src/AuthController.java:10)"));
  assert.ok(lines.includes("- UserController (src/UserController.java:5)"));
});

test("shows a stale warning when present", () => {
  const result = {
    queryType: "tag:service",
    title: "Services",
    count: 0,
    items: [],
    staleWarning: "Index is out of date — run `brain index`.",
  };
  const lines = formatLocalResult(result);
  assert.ok(lines[0].startsWith("! "));
  assert.ok(lines.includes("(no results)"));
});

test("renders grouped results with owner headers and child items", () => {
  const result = {
    queryType: "grouped_routes",
    title: "Routes Grouped by Owner",
    count: 2,
    items: [],
    groups: [
      {
        owner: "UserController",
        ownerKind: "class",
        ownerFile: "UserController.java",
        items: [
          { name: "GET /api/users", kind: "method", filePath: "UserController.java", startLine: 20, endLine: 25 },
          { name: "POST /api/users", kind: "method", filePath: "UserController.java", startLine: 30, endLine: 35 },
        ],
      },
    ],
    staleWarning: null,
  };
  const lines = formatLocalResult(result);
  assert.strictEqual(lines[0], "Routes Grouped by Owner: 2");
  assert.ok(lines.includes("UserController [class]"));
  assert.ok(lines.includes("  - GET /api/users (UserController.java:20)"));
  assert.ok(lines.includes("  - POST /api/users (UserController.java:30)"));
});

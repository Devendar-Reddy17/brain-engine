const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const { extractPatchPaths, assertPatchPathsSafe } = require("../dist/patch/patchApply");

const REPO = path.resolve("/repo");

test("extracts patched file paths", () => {
  const patch = "diff --git a/src/A.java b/src/A.java\n--- a/src/A.java\n+++ b/src/A.java\n@@ -1 +1 @@\n-x\n+y\n";
  const paths = extractPatchPaths(patch);
  assert.deepStrictEqual(paths, ["src/A.java"]);
});

test("accepts paths inside the repo", () => {
  const patch = "--- a/src/A.java\n+++ b/src/A.java\n@@ -1 +1 @@\n-x\n+y\n";
  const paths = assertPatchPathsSafe(REPO, patch);
  assert.ok(paths.includes("src/A.java"));
});

test("rejects absolute paths", () => {
  const patch = "--- a//etc/passwd\n+++ b//etc/passwd\n@@ -1 +1 @@\n-x\n+y\n";
  assert.throws(() => assertPatchPathsSafe(REPO, patch), /absolute|escapes/i);
});

test("rejects paths escaping the repo root", () => {
  const patch = "--- a/../../secret.txt\n+++ b/../../secret.txt\n@@ -1 +1 @@\n-x\n+y\n";
  assert.throws(() => assertPatchPathsSafe(REPO, patch), /escapes/i);
});

test("rejects a patch with no files", () => {
  assert.throws(() => assertPatchPathsSafe(REPO, "no diff here"), /does not reference/i);
});

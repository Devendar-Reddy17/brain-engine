const test = require("node:test");
const assert = require("node:assert");

const { extractPatch } = require("../dist/ai/patchExtractor");

test("extracts a fenced diff block", () => {
  const response = "Here is the patch:\n```diff\ndiff --git a/A.java b/A.java\n--- a/A.java\n+++ b/A.java\n@@ -1 +1 @@\n-old\n+new\n```\n";
  const patch = extractPatch(response);
  assert.match(patch, /diff --git a\/A\.java b\/A\.java/);
  assert.ok(patch.endsWith("\n"));
});

test("extracts a raw (unfenced) diff", () => {
  const response = "--- a/A.java\n+++ b/A.java\n@@ -1 +1 @@\n-old\n+new\n";
  const patch = extractPatch(response);
  assert.match(patch, /\+\+\+ b\/A\.java/);
});

test("throws when no diff is present", () => {
  assert.throws(() => extractPatch("This is just prose with no patch."));
});

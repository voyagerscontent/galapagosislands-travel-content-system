#!/usr/bin/env node
/*
 * Sync test: proves the n8n JavaScript twin stays behavior-identical to the
 * Python normalizer.
 *
 * It does three things:
 *   1. Extracts the `jsCode` embedded in automation/n8n_normalize_node.json,
 *      compiles it for both MODE = 'content-safe' and MODE = 'aggressive',
 *      and checks every shared fixture (fixtures.json) matches the expected
 *      output.
 *   2. Confirms the n8n node's hardcoded PROTECT list matches the fixtures'
 *      protect list (so the two twins are actually comparable).
 *   3. Cross-checks: runs the SAME inputs through normalize.py and asserts the
 *      Python output is byte-identical to the JS output. This is the guard that
 *      catches drift between the two implementations.
 *
 * No dependencies beyond Node's stdlib + a python3 on PATH.
 * Run: node sync_test.js   ->  exits 0 and prints "SYNC OK" if the twins agree.
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const DIR = __dirname;
const NODE_JSON = path.join(DIR, "..", "automation", "n8n_normalize_node.json");
const FIXTURES = path.join(DIR, "fixtures.json");
const PY = path.join(DIR, "normalize.py");

const fails = [];
function check(name, got, expected) {
  if (got !== expected) {
    fails.push(`${name}\n    expected: ${JSON.stringify(expected)}\n    got:      ${JSON.stringify(got)}`);
  } else {
    console.log(`  ok  ${name}`);
  }
}

// ---- Load the n8n node and its embedded code -------------------------------
const nodeDoc = JSON.parse(fs.readFileSync(NODE_JSON, "utf8"));
const rawCode = nodeDoc.nodes[0].parameters.jsCode;
const fixtures = JSON.parse(fs.readFileSync(FIXTURES, "utf8"));

// Compile the embedded code into a callable normalize() for a given MODE.
// The node ends with `return items.map(...)`; we strip that and expose the
// inner normalize function instead, and force MODE via replacement.
function buildNormalizer(mode) {
  let code = rawCode
    .replace(/const MODE\s*=\s*'[^']*';/, `const MODE = '${mode}';`)
    .replace(/return items\.map[\s\S]*$/, "return normalize;");
  // Wrap so `items` reference (removed) doesn't matter and we return the fn.
  const factory = new Function(`${code}`);
  return factory();
}

// ---- 2. PROTECT-list parity ------------------------------------------------
const protectMatch = rawCode.match(/const PROTECT\s*=\s*\[([^\]]*)\]/);
const nodeProtect = protectMatch
  ? protectMatch[1].split(",").map((s) => s.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean)
  : [];
check(
  "n8n PROTECT list matches fixtures.protect",
  JSON.stringify(nodeProtect),
  JSON.stringify(fixtures.protect)
);

// ---- 1. JS output matches expected fixtures --------------------------------
const nsafe = buildNormalizer("content-safe");
for (const f of fixtures.content_safe) {
  check(`[js content-safe] ${f.name}`, nsafe(f.in), f.out);
}
const nagg = buildNormalizer("aggressive");
for (const f of fixtures.aggressive) {
  check(`[js aggressive] ${f.name}`, nagg(f.in), f.out);
}

// ---- 3. Cross-check JS == Python for every fixture input -------------------
// Batch all inputs to Python once (one JSON in, one JSON out) to keep it fast.
function pythonNormalizeBatch(items) {
  // items: [{text, aggressive, protect:[...]}]
  const script = `
import sys, json
sys.path.insert(0, ${JSON.stringify(DIR)})
from normalize import normalize
data = json.load(sys.stdin)
out = []
for it in data:
    out.append(normalize(it["text"], aggressive=it["aggressive"],
                          protect=(it["protect"] or None)))
sys.stdout.write(json.dumps(out, ensure_ascii=False))
`;
  const res = execFileSync("python3", ["-c", script], {
    input: JSON.stringify(items),
    encoding: "utf8",
  });
  return JSON.parse(res);
}

const parityItems = [
  ...fixtures.content_safe.map((f) => ({ text: f.in, aggressive: false, protect: [] })),
  ...fixtures.aggressive.map((f) => ({ text: f.in, aggressive: true, protect: fixtures.protect })),
];
const pyOut = pythonNormalizeBatch(parityItems);
const jsOut = [
  ...fixtures.content_safe.map((f) => nsafe(f.in)),
  ...fixtures.aggressive.map((f) => nagg(f.in)),
];
for (let i = 0; i < parityItems.length; i++) {
  const label = i < fixtures.content_safe.length
    ? `content-safe[${i}]`
    : `aggressive[${i - fixtures.content_safe.length}]`;
  check(`[parity JS==PY] ${label}`, jsOut[i], pyOut[i]);
}

// ---- Summary ---------------------------------------------------------------
console.log("");
if (fails.length) {
  console.error(`SYNC FAILED  -  ${fails.length} mismatch(es):\n`);
  for (const f of fails) console.error("  X  " + f);
  process.exit(1);
}
console.log("SYNC OK  -  n8n JS twin is byte-identical to normalize.py across all fixtures");
process.exit(0);

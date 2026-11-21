import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("../site/node_modules/typescript");
const sourcePath = "site/src/app/cabinet/cabinet-client.tsx";
const baseline = execFileSync("git", ["show", `HEAD:${sourcePath}`], {
  encoding: "utf8",
});
const current = readFileSync(sourcePath, "utf8");
const printer = ts.createPrinter({ removeComments: true });

function inventory(text) {
  const source = ts.createSourceFile(
    "cabinet.tsx",
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const result = {
    fetchCalls: [],
    analyticsCalls: [],
    handlers: [],
    functions: [],
  };
  const print = (node) =>
    printer.printNode(ts.EmitHint.Unspecified, node, source);
  function visit(node) {
    if (ts.isCallExpression(node)) {
      if (node.expression.getText(source) === "fetch") {
        const options = node.arguments[1];
        const entries = options && ts.isObjectLiteralExpression(options)
          ? new Map(options.properties.filter(ts.isPropertyAssignment)
              .map((property) => [property.name.getText(source).replace(/["']/g, ""), property.initializer]))
          : new Map();
        const endpoint = print(node.arguments[0]);
        const method = entries.has("method") ? print(entries.get("method")) : '"GET"';
        // Additive payload fields (such as delivery city/radius) are allowed.
        // Existing endpoint, method, headers and body fields must still exist.
        const prefix = `${endpoint} ${method}`;
        result.fetchCalls.push(prefix);
        for (const key of ["credentials", "headers"]) {
          if (entries.has(key)) result.fetchCalls.push(`${prefix} ${key}=${print(entries.get(key))}`);
        }
        const body = entries.get("body");
        const payload = body && ts.isCallExpression(body) && body.expression.getText(source) === "JSON.stringify"
          ? body.arguments[0] : null;
        if (payload && ts.isObjectLiteralExpression(payload)) {
          for (const field of payload.properties) {
            if (ts.isPropertyAssignment(field) || ts.isShorthandPropertyAssignment(field))
              result.fetchCalls.push(`${prefix} body.${field.name.getText(source)}`);
          }
        }
      }
      if (node.expression.getText(source) === "trackGoal")
        result.analyticsCalls.push(print(node));
    }
    if (
      ts.isJsxAttribute(node) &&
      /^on[A-Z]/.test(node.name.getText(source)) &&
      node.initializer
    ) {
      // Runtime handler behavior is verified by the mocked browser suite.
      result.handlers.push(node.name.getText(source));
    }
    // Helper bodies intentionally change during a fix; retain their named entry points.
    if (ts.isFunctionDeclaration(node) && node.name && node.name.text !== "CabinetClient")
      result.functions.push(node.name.text);
    ts.forEachChild(node, visit);
  }
  visit(source);
  return result;
}

function multiset(values) {
  const counts = new Map();
  values.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return counts;
}

const before = inventory(baseline),
  after = inventory(current);
for (const category of Object.keys(before)) {
  const available = multiset(after[category]);
  for (const [value, count] of multiset(before[category])) {
    assert.ok(
      (available.get(value) || 0) >= count,
      `${category}: removed or modified contract:\n${value}`,
    );
  }
}
const summary = Object.fromEntries(
  Object.keys(before).map((category) => [
    category,
    {
      before: before[category].length,
      after: after[category].length,
      preserved: true,
    },
  ]),
);
if (process.argv[2])
  writeFileSync(
    process.argv[2],
    JSON.stringify({ status: "passed", summary }, null, 2),
  );
console.log(
  "PASS: static endpoints, methods, existing payload fields, analytics, event binding counts and helper names retained; behavior requires browser QA",
);
console.log(JSON.stringify(summary));

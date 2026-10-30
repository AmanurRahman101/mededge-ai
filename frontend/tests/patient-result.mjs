import { build } from "esbuild";
import { createRequire } from "node:module";
import { strict as assert } from "node:assert";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";

const require = createRequire(import.meta.url);
const fixture = { status: "reviewing", pseudonym: "TEST", extraction: { rows: [], medications: [], advised_tests: [{ raw_name: "CRP" }, { raw_name: "RBS" }] } };
const plugin = {
  name: "test-workspace",
  setup(build) {
    build.onResolve({ filter: /^@phosphor-icons\/react$/ }, () => ({ path: "icons", namespace: "fixture" }));
    build.onResolve({ filter: /^\.\/(store|useRun|api)$/ }, args => ({ path: args.path, namespace: "fixture" }));
    build.onLoad({ filter: /.*/, namespace: "fixture" }, args => {
      if (args.path === "icons") return { contents: "exports.Microphone = () => null; exports.Stop = () => null;", loader: "js" };
      if (args.path === "./store") return { contents: "exports.useApp = selector => selector({ setScreen() {} });", loader: "js" };
      if (args.path === "./useRun") return { contents: `exports.useRun = () => ({run: ${JSON.stringify(fixture)}, events: [], error: null});`, loader: "js" };
      return { contents: 'exports.apiBase = ""; exports.listCases = async () => [];', loader: "js" };
    });
  }
};
const result = await build({ entryPoints: ["src/Patient.tsx"], bundle: true, platform: "node", format: "cjs", packages: "external", write: false, plugins: [plugin], jsx: "automatic" });
const Module = require("node:module");
const module = new Module(`${process.cwd()}/tests/patient-bundle.cjs`);
module.filename = `${process.cwd()}/tests/patient-bundle.cjs`;
module.paths = Module._nodeModulePaths(process.cwd());
module._compile(result.outputFiles[0].text, module.filename);
const html = renderToStaticMarkup(React.createElement(module.exports.Patient));
assert.match(html, /CRP/, "Patient result must show extracted advised tests");
assert.match(html, /RBS/, "Patient result must show every extracted advised test");
const doctorResult = await build({ entryPoints: ["src/Doctor.tsx"], bundle: true, platform: "node", format: "cjs", packages: "external", write: false, plugins: [plugin], jsx: "automatic" });
const doctorModule = new Module(`${process.cwd()}/tests/doctor-bundle.cjs`);
doctorModule.filename = `${process.cwd()}/tests/doctor-bundle.cjs`;
doctorModule.paths = Module._nodeModulePaths(process.cwd());
doctorModule._compile(doctorResult.outputFiles[0].text, doctorModule.filename);
const doctorHtml = renderToStaticMarkup(React.createElement(doctorModule.exports.Doctor));
assert.match(doctorHtml, /CRP/, "Doctor result must show extracted advised tests");
assert.match(doctorHtml, /RBS/, "Doctor result must show every extracted advised test");
assert.match(doctorHtml, /not included in the FHIR export/);
console.log("Patient and doctor results show extracted advised tests");

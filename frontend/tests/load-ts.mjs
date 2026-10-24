import fs from 'node:fs/promises';
import path from 'node:path';

import ts from 'typescript';

// Run the production TypeScript utilities with Node's built-in test runner.
// Only Vite's compile-time environment is substituted; application code is real.
export async function moduleUrl(file) {
  let source = await fs.readFile(file, 'utf8');
  source = source.replaceAll('import.meta.env.VITE_API_URL', JSON.stringify('https://api.example.test/'));
  let js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  for (const match of [...js.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const specifier = match[1];
    let resolved;
    if (specifier.startsWith('.') || specifier.startsWith('@/')) {
      const base = specifier.startsWith('@/')
        ? new URL('../src/' + specifier.slice(2), import.meta.url)
        : new URL(specifier, file);
      let target;
      for (const extension of ['.ts', '.tsx']) {
        const candidate = new URL(base.href + extension);
        try { await fs.access(candidate); target = candidate; break; } catch { /* Try TSX. */ }
      }
      if (!target) throw new Error('Cannot resolve ' + specifier);
      resolved = await moduleUrl(target);
    } else resolved = import.meta.resolve(specifier);
    js = js.replace(match[0], `from ${JSON.stringify(resolved)}`);
  }
  return 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
}
export async function loadTs(name) {
  const file = new URL(path.join('../src/', name), import.meta.url);
  return import(await moduleUrl(file));
}

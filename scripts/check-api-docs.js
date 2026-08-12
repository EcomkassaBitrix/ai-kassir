import { readFileSync, readdirSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const backendDir = path.join(root, 'backend');
const apiDocsFile = path.join(root, 'src/data/apiDocs.ts');

// Реальные backend-функции = папки в /backend, у которых есть index.py
const backendFunctions = readdirSync(backendDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

// ID методов, описанных в src/data/apiDocs.ts
const apiDocsContent = readFileSync(apiDocsFile, 'utf-8');
const documentedIds = [...apiDocsContent.matchAll(/id:\s*'([\w-]+)'/g)]
  .map((m) => m[1])
  .sort();

const missingInDocs = backendFunctions.filter((f) => !documentedIds.includes(f));
const staleInDocs = documentedIds.filter((d) => !backendFunctions.includes(d));

if (missingInDocs.length === 0 && staleInDocs.length === 0) {
  console.log(`✅ API.md / apiDocs.ts в порядке: все ${backendFunctions.length} backend-методов описаны.`);
  process.exit(0);
}

console.warn('⚠️  Документация API (src/data/apiDocs.ts) разошлась с backend/:');

if (missingInDocs.length > 0) {
  console.warn(`  Нет описания для функций: ${missingInDocs.join(', ')}`);
}

if (staleInDocs.length > 0) {
  console.warn(`  Описаны методы, которых больше нет в backend/: ${staleInDocs.join(', ')}`);
}

console.warn('  Обнови src/data/apiDocs.ts (и API.md), чтобы документация оставалась актуальной.');

// Не роняем билд — только предупреждаем
process.exit(0);

// Copies the LOCKED Stage 8 classifier prompt into functions/_lib as a .txt
// text module so wrangler's esbuild can inline it into the Pages Function
// bundle (esbuild has a text loader for .txt but none for .md).
//
// scripts/stage8/classifier-eval/classifier_prompt.md remains the single
// source of truth — both the eval harness (run_eval.py) and the Function read
// from it. The .txt copy is gitignored and regenerated on every `npm run
// build`; if it's missing, the Functions bundle fails loudly at build time.
import { copyFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
copyFileSync(
  join(root, 'scripts', 'stage8', 'classifier-eval', 'classifier_prompt.md'),
  join(root, 'functions', '_lib', 'classifier-prompt.generated.txt'),
);

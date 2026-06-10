import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(new URL('..', import.meta.url).pathname);
const componentPath = path.join(root, 'src/components/GameEndingOverlay.tsx');
const pagePath = path.join(root, 'src/pages/SessionDeskPage.tsx');
const stylesPath = path.join(root, 'src/styles.css');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(fs.existsSync(componentPath), 'GameEndingOverlay component is missing');
const component = fs.readFileSync(componentPath, 'utf8');
const page = fs.readFileSync(pagePath, 'utf8');
const styles = fs.readFileSync(stylesPath, 'utf8');
const adapter = fs.readFileSync(path.join(root, 'src/adapters/sessionAdapter.ts'), 'utf8');

for (const token of [
  'GAME CLEAR',
  'GAME FAILED',
  '사건 해결',
  '잘못된 범인',
  'ending-overlay victory',
  'ending-overlay defeat',
  'role="dialog"',
]) {
  assert(component.includes(token), `GameEndingOverlay must include ${token}`);
}

assert(page.includes('<GameEndingOverlay'), 'SessionDeskPage must render GameEndingOverlay when session.result exists');
assert(page.includes('onOpenDossier'), 'GameEndingOverlay must offer reopening the final dossier');
assert(styles.includes('.ending-overlay-backdrop'), 'ending overlay backdrop styles are missing');
assert(styles.includes('.ending-overlay.victory'), 'victory ending style is missing');
assert(styles.includes('.ending-overlay.defeat'), 'defeat ending style is missing');
assert(adapter.includes('session.accusation?.verdict'), 'loaded solved/failed sessions must restore result from persisted accusation');
assert(adapter.includes('outcome: accusationResult.verdict === "correct" ? "victory" : "defeat"'), 'adapter must map correct to victory and wrong to defeat');

console.log('ending-ui smoke passed');

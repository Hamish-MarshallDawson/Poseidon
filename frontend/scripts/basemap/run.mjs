// npm run basemap [fetch|build|glyphs|all]: runs the Python basemap pipeline in scripts/basemap/.venv (made on first use
// with `uv` if present, else `python3 -m venv`). Default `all`: fetch (resumable) then build. Glyphs are committed, so
// `glyphs` only needs running when the fonts or ranges change.
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const win = process.platform === 'win32'
const py = join(here, '.venv', win ? 'Scripts/python.exe' : 'bin/python')
const run = (cmd, args) => execFileSync(cmd, args, { stdio: 'inherit', cwd: here })
const has = (cmd) => { try { execFileSync(cmd, ['--version'], { stdio: 'ignore' }); return true } catch { return false } }

if (!existsSync(py)) {
  if (has('uv')) { run('uv', ['venv', '.venv']); run('uv', ['pip', 'install', '--python', py, '-r', 'requirements.txt']) }
  else { run(win ? 'python' : 'python3', ['-m', 'venv', '.venv']); run(py, ['-m', 'pip', 'install', '-r', 'requirements.txt']) }
}
const step = process.argv[2] ?? 'all'
const steps = { fetch: ['fetch_ofm.py'], build: ['build.py'], glyphs: ['glyphs.py'], all: ['fetch_ofm.py', 'build.py'] }[step]
if (!steps) { console.error('usage: npm run basemap [fetch|build|glyphs|all]'); process.exit(2) }
for (const s of steps) run(py, ['-u', s])

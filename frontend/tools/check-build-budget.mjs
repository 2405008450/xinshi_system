import { readFileSync, statSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { join } from 'node:path'

const distDir = join(process.cwd(), 'dist')
const manifest = JSON.parse(
  readFileSync(join(distDir, '.vite', 'manifest.json'), 'utf8')
)

function findEntry(source) {
  const exact = manifest[source]
  if (exact) return exact
  return Object.values(manifest).find((entry) => entry.src === source)
}

function staticClosure(entry) {
  const visited = new Set()
  const visit = (item) => {
    if (!item || visited.has(item.file)) return
    visited.add(item.file)
    for (const imported of item.imports || []) visit(manifest[imported])
  }
  visit(entry)
  return [...visited]
}

function gzipBytes(files) {
  return files.reduce((total, file) => {
    const path = join(distDir, file)
    return total + gzipSync(readFileSync(path)).byteLength
  }, 0)
}

function assertBudget(label, source, maxBytes) {
  const entry = findEntry(source)
  if (!entry) throw new Error(`Build budget entry not found: ${source}`)
  const files = staticClosure(entry)
  const bytes = gzipBytes(files)
  const kb = (bytes / 1024).toFixed(1)
  console.log(`${label}: ${kb} KiB gzip (${files.length} static files)`)
  if (bytes > maxBytes) {
    throw new Error(`${label} exceeds budget: ${kb} KiB > ${maxBytes / 1024} KiB`)
  }
  return files
}

const entryFiles = assertBudget('Unauthenticated entry', 'index.html', 250 * 1024)
const workbenchFiles = assertBudget(
  'Default workbench',
  'src/views/schedule/WorkDashboard.vue',
  500 * 1024,
)

const closure = [...new Set([...entryFiles, ...workbenchFiles])]
const univerFiles = closure.filter((file) => /univer/i.test(file))
if (univerFiles.length) {
  throw new Error(`Univer leaked into default workbench: ${univerFiles.join(', ')}`)
}

for (const file of closure) statSync(join(distDir, file))
console.log('Build budgets passed; Univer remains behind an async boundary.')

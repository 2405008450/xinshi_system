import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'
import { reportPackagePath, readReportPackage } from './transcription-report-package.mjs'

// 更新报告时，将完整展示目录打包；不收入仅供内部追溯的核对记录。
const sourceDirectory = process.argv[2]
if (!sourceDirectory) throw new Error('用法：node tools/pack-transcription-report.mjs <报告目录>')
const files = {}
function collect(directory, prefix = '') {
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, 'en'))) {
    if (entry.name === '核对记录.json') continue
    const name = prefix + entry.name
    if (entry.isDirectory()) collect(join(directory, entry.name), `${name}/`)
    else if (entry.isFile()) files[name] = readFileSync(join(directory, entry.name), 'utf8')
  }
}
collect(resolve(sourceDirectory))
if (!files['综合分析报告.html'] || !files['details/ko_kr.js']) throw new Error('报告目录缺少主页面或语种明细')
mkdirSync(dirname(reportPackagePath), { recursive: true })
const packed = gzipSync(JSON.stringify(files), { level: 9 })
writeFileSync(reportPackagePath, packed)
const restored = readReportPackage()
for (const [name, content] of Object.entries(files)) {
  if (restored[name] !== content) throw new Error(`打包校验失败：${name}`)
}
console.log(`报告已打包并校验：${Object.keys(files).length} 个文件 → ${(packed.length / 1024 / 1024).toFixed(2)} MiB，${reportPackagePath}`)

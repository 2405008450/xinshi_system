import { readFileSync, statSync } from 'node:fs'
import { gunzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'

export const reportBase = 'reports/minority-transcription-20261113/'
export const reportPackagePath = fileURLToPath(new URL('../reports/minority-transcription-20261113.json.gz', import.meta.url))

export function readReportPackage(packagePath = reportPackagePath) {
  const files = JSON.parse(gunzipSync(readFileSync(packagePath)).toString('utf8'))
  for (const [name, content] of Object.entries(files)) {
    if (!name || name.startsWith('/') || name.includes('\\') || name.split('/').some(part => !part || part === '.' || part === '..') || typeof content !== 'string') {
      throw new Error(`Invalid report package entry: ${name}`)
    }
  }
  return files
}

const contentTypes = {
  html: 'text/html', js: 'text/javascript', json: 'application/json',
  csv: 'text/csv', txt: 'text/plain',
}

// 开发时按原地址提供文件；构建时输出相同目录，保留报告的按语种加载能力。
export function transcriptionReportPlugin(packagePath = reportPackagePath) {
  return {
    name: 'transcription-report-package',
    configureServer(server) {
      let cachedFiles
      let cachedMtime
      server.watcher.add(packagePath)
      server.middlewares.use((req, res, next) => {
        let pathname
        try { pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname) }
        catch { res.statusCode = 400; res.end(); return }
        const prefix = `${server.config.base}${reportBase}`
        if (!pathname.startsWith(prefix)) return next()
        if (!['GET', 'HEAD'].includes(req.method)) { res.statusCode = 405; res.end(); return }
        try {
          const mtime = statSync(packagePath).mtimeMs
          if (!cachedFiles || cachedMtime !== mtime) {
            cachedFiles = readReportPackage(packagePath)
            cachedMtime = mtime
          }
          const name = pathname.slice(prefix.length)
          if (!Object.hasOwn(cachedFiles, name)) { res.statusCode = 404; res.end(); return }
          res.setHeader('Content-Type', `${contentTypes[name.split('.').pop()] || 'application/octet-stream'}; charset=utf-8`)
          res.setHeader('Cache-Control', 'no-cache')
          res.end(req.method === 'HEAD' ? undefined : cachedFiles[name])
        } catch (error) { next(error) }
      })
    },
    generateBundle() {
      for (const [name, source] of Object.entries(readReportPackage(packagePath))) {
        this.emitFile({ type: 'asset', fileName: `${reportBase}${name}`, source })
      }
    },
  }
}

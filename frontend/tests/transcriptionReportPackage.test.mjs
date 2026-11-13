import test from 'node:test'
import assert from 'node:assert/strict'
import { readReportPackage, reportBase, transcriptionReportPlugin } from '../tools/transcription-report-package.mjs'

test('报告包构建输出保留主页面、折叠区与所有语种明细', () => {
  const files = readReportPackage()
  assert.match(files['综合分析报告.html'], /id="sourcePathsContent" hidden/)
  assert.ok(files['details/ko_kr.js'].startsWith('window.ASR_DETAILS='))
  const emitted = []
  transcriptionReportPlugin().generateBundle.call({ emitFile: file => emitted.push(file) })
  assert.equal(emitted.length, Object.keys(files).length)
  for (const file of emitted) {
    assert.equal(file.source, files[file.fileName.slice(reportBase.length)])
  }
})

test('开发服务支持中文地址、按语种请求、HEAD 与不存在的文件', () => {
  let middleware
  transcriptionReportPlugin().configureServer({
    config: { base: '/' }, watcher: { add() {} },
    middlewares: { use: handler => { middleware = handler } },
  })
  function request(name, method = 'GET') {
    const response = { headers: {}, setHeader(key, value) { this.headers[key] = value }, end(body) { this.body = body } }
    middleware({ url: `/${reportBase}${encodeURI(name)}`, method }, response, error => { throw error || new Error('报告请求未被处理') })
    return response
  }
  const page = request('综合分析报告.html')
  assert.match(page.headers['Content-Type'], /^text\/html/)
  assert.match(page.body, /sourcePathsToggle/)
  assert.match(request('details/ko_kr.js?v=2026').body, /^window\.ASR_DETAILS=/)
  assert.equal(request('details/ko_kr.js', 'HEAD').body, undefined)
  assert.equal(request('missing.js').statusCode, 404)
})

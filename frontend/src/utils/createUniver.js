import { IAuthzIoService, IMentionIOService, IUndoRedoService, LogLevel, Univer } from '@univerjs/core'
import { FUniver } from '@univerjs/core/lib/facade'

// @univerjs/presets 的根入口还会重导出整个 themes 包及大量语言资源。
// 项目只需要这个很小的装配函数，因此在本地实现以避免把无关主题/语种拉入业务块。
export const createUniver = (options) => {
  const { presets, plugins, collaboration, override = [], ...config } = options
  if (collaboration) {
    override.push([IUndoRedoService, null], [IAuthzIoService, null], [IMentionIOService, null])
  }
  const univer = new Univer({ logLevel: LogLevel.WARN, ...config, override })
  const registry = new Map()
  presets?.forEach((entry) => {
    const preset = Array.isArray(entry) ? entry[0] : entry
    preset.plugins.forEach((pluginEntry) => {
      const [plugin, pluginOptions] = Array.isArray(pluginEntry) ? pluginEntry : [pluginEntry]
      registry.delete(plugin.pluginName)
      registry.set(plugin.pluginName, { plugin, options: pluginOptions })
    })
  })
  plugins?.forEach((entry) => {
    const [plugin, pluginOptions] = Array.isArray(entry) ? entry : [entry]
    if (registry.has(plugin.pluginName)) throw new Error(`Univer 插件重复注册：${plugin.pluginName}`)
    registry.set(plugin.pluginName, { plugin, options: pluginOptions })
  })
  registry.forEach(({ plugin, options: pluginOptions }) => univer.registerPlugin(plugin, pluginOptions))
  return { univer, univerAPI: FUniver.newAPI(univer) }
}

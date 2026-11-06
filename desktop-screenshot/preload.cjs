const { contextBridge, ipcRenderer } = require('electron')
contextBridge.exposeInMainWorld('xinshiDesktop', Object.freeze({
  prepareStatementFile: data => {
    if(!document.hasFocus()||!navigator.userActivation.isActive)return Promise.reject(Error('请点击准备对账单文件'))
    return ipcRenderer.invoke('xinshi:prepare-statement-file',data)
  },
  prepareStatementPdf: data => {
    if(!document.hasFocus()||!navigator.userActivation.isActive)return Promise.reject(Error('请点击准备PDF文件'))
    return ipcRenderer.invoke('xinshi:prepare-statement-pdf',data)
  },
  dragStatementFile: token => {
    if(document.hasFocus())ipcRenderer.send('xinshi:drag-statement-file',token)
  },
  captureScreen: () => {
    if (!document.hasFocus() || !navigator.userActivation.isActive) return Promise.reject(Error('请点击截图按钮或按下截图快捷键'))
    return ipcRenderer.invoke('xinshi:capture-screen')
  },
}))

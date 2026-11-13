const { contextBridge, ipcRenderer } = require('electron')
contextBridge.exposeInMainWorld('xinshiDesktop', Object.freeze({
  chooseTranslationFolder:()=>{
    if(!document.hasFocus()||!navigator.userActivation.isActive)return Promise.reject(Error('请点击选择本地文件夹'))
    return ipcRenderer.invoke('xinshi:choose-translation-folder')
  },
  prepareStatementFile: data => {
    if(!document.hasFocus()||!navigator.userActivation.isActive)return Promise.reject(Error('请点击准备对账单文件'))
    return ipcRenderer.invoke('xinshi:prepare-statement-file',data)
  },
  prepareStatementPdf: data => {
    if(!document.hasFocus()||!navigator.userActivation.isActive)return Promise.reject(Error('请点击准备PDF文件'))
    return ipcRenderer.invoke('xinshi:prepare-statement-pdf',data)
  },
  prepareInvoiceFile: data => {
    if (!document.hasFocus() || !navigator.userActivation.isActive) return Promise.reject(Error('请点击准备桌面拖出'))
    return ipcRenderer.invoke('xinshi:prepare-invoice-file', data)
  },
  dragStatementFile: token => {
    if(document.hasFocus())ipcRenderer.send('xinshi:drag-statement-file',token)
  },
  captureScreen: () => {
    if (!document.hasFocus() || !navigator.userActivation.isActive) return Promise.reject(Error('请点击截图按钮或按下截图快捷键'))
    return ipcRenderer.invoke('xinshi:capture-screen')
  },
}))

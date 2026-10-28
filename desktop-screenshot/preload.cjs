const { contextBridge, ipcRenderer } = require('electron')
contextBridge.exposeInMainWorld('xinshiDesktop', Object.freeze({
  captureScreen: () => {
    if (!document.hasFocus() || !navigator.userActivation.isActive) return Promise.reject(Error('请点击截图按钮或按下截图快捷键'))
    return ipcRenderer.invoke('xinshi:capture-screen')
  },
}))

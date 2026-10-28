const { app, BrowserWindow, desktopCapturer, ipcMain, screen, dialog } = require('electron')
const path = require('node:path')
const APP_URL = 'http://localhost:3000/'
let mainWindow, capturing = false
const trusted = url => { try { return new URL(url).origin === new URL(APP_URL).origin } catch { return false } }

app.whenReady().then(() => {
  mainWindow = new BrowserWindow({
    width: 1440, height: 960, title: '项目管理 · 桌面版',
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true },
  })
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  mainWindow.webContents.on('will-navigate', (event, url) => { if (!trusted(url)) event.preventDefault() })
  mainWindow.webContents.on('will-redirect', (event, url) => { if (!trusted(url)) event.preventDefault() })
  mainWindow.webContents.session.setPermissionRequestHandler((_contents, permission, callback) => callback(permission === 'clipboard-sanitized-write'))
  ipcMain.handle('xinshi:capture-screen', async event => {
    if (process.platform !== 'win32') throw Error('免询问截屏入口目前仅支持 Windows')
    if (event.sender !== mainWindow.webContents || event.senderFrame !== mainWindow.webContents.mainFrame || !trusted(event.senderFrame.url) || !mainWindow.isFocused()) throw Error('请在系统桌面窗口中点击截图')
    if (capturing) throw Error('正在截图，请稍候')
    capturing = true
    try {
      const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())
      const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: Math.round(display.size.width * display.scaleFactor), height: Math.round(display.size.height * display.scaleFactor) } })
      const source = sources.find(item => item.display_id === String(display.id))
      if (!source || source.thumbnail.isEmpty()) throw Error('无法获取当前屏幕图像')
      return source.thumbnail.toDataURL()
    } finally { capturing = false }
  })
  mainWindow.loadURL(APP_URL).catch(() => dialog.showErrorBox('本地服务未启动', '请先启动本地系统服务：http://localhost:3000/，再重新打开桌面入口。'))
})
app.on('window-all-closed', () => app.quit())

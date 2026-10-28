const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm')
test('桌面截屏仅允许受信任主窗口，并选取鼠标所在显示器',async()=>{
 let handler,window,options,captures=0
 const mainFrame={url:'http://localhost:3000/translation-details'}
 class BrowserWindow {
  constructor(config){options=config;window=this;this.focused=true;this.webContents={mainFrame,setWindowOpenHandler(){},on(){},session:{setPermissionRequestHandler(){}}}}
  isFocused(){return this.focused}
  loadURL(){return Promise.resolve()}
 }
 const electron={app:{whenReady:()=>Promise.resolve(),on(){}},BrowserWindow,dialog:{},screen:{getCursorScreenPoint:()=>({x:100,y:200}),getDisplayNearestPoint:()=>({id:2,size:{width:1920,height:1080},scaleFactor:1.5})},ipcMain:{handle:(_name,callback)=>{handler=callback}},desktopCapturer:{getSources:async config=>{captures++;assert.equal(config.thumbnailSize.width,2880);return [{display_id:'2',thumbnail:{isEmpty:()=>false,toDataURL:()=> 'data:image/png;base64,test'}}]}}}
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../main.cjs'),'utf8'),{require:name=>name==='electron'?electron:require(name),__dirname:require('node:path').join(__dirname,'..'),process:{platform:'win32'},URL})
 await Promise.resolve()
 assert.equal(options.webPreferences.sandbox,true);assert.equal(options.webPreferences.nodeIntegration,false)
 const event={sender:window.webContents,senderFrame:mainFrame}
 assert.equal(await handler(event),'data:image/png;base64,test')
 await assert.rejects(handler({...event,senderFrame:{url:mainFrame.url}}),/系统桌面窗口/)
 mainFrame.url='https://untrusted.example/'
 await assert.rejects(handler(event),/系统桌面窗口/)
 mainFrame.url='http://localhost:3000/';window.focused=false
 await assert.rejects(handler(event),/系统桌面窗口/)
 assert.equal(captures,1)
})

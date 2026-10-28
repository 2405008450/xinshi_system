import test from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_SCREENSHOT_SHORTCUT, shortcutFromEvent, shortcutLabel, readScreenshotShortcut } from '../src/utils/screenshotShortcut.js'
const event=(code, modifiers={})=>({code,...modifiers})
test('默认 Alt+A，并严格区分其他修饰键及物理按键',()=>{
 assert.equal(DEFAULT_SCREENSHOT_SHORTCUT,'Alt+KeyA')
 assert.equal(shortcutFromEvent(event('KeyA',{altKey:true})),'Alt+KeyA')
 assert.equal(shortcutFromEvent(event('KeyA',{altKey:true,shiftKey:true})),'Alt+Shift+KeyA')
 assert.equal(shortcutFromEvent(event('KeyS',{ctrlKey:true,shiftKey:true})),'Control+Shift+KeyS')
 assert.equal(shortcutLabel('Control+Alt+Digit1'),'Ctrl+Alt+1')
})
test('忽略普通输入、长按、输入法组合及保留的浏览器快捷键',()=>{
 for(const value of [event('KeyA'),event('AltLeft',{altKey:true}),event('KeyA',{altKey:true,repeat:true}),event('KeyA',{altKey:true,isComposing:true}),event('KeyW',{ctrlKey:true}),event('KeyV',{ctrlKey:true}),event('F4',{altKey:true}),event('F5',{altKey:true})]) assert.equal(shortcutFromEvent(value),null)
})
test('个人配置按账号读取，异常或无效配置退回 Alt+A',()=>{
 const values=new Map([['screenshot-shortcut:alice','Control+Shift+KeyS'],['screenshot-shortcut:bob','Alt+Digit1']])
 const storage={getItem:key=>values.get(key)??null}
 assert.equal(readScreenshotShortcut(storage,'alice'),'Control+Shift+KeyS')
 assert.equal(readScreenshotShortcut(storage,'bob'),'Alt+Digit1')
 assert.equal(readScreenshotShortcut(storage,'new'),'Alt+KeyA')
 values.set('screenshot-shortcut:alice','KeyA')
 assert.equal(readScreenshotShortcut(storage,'alice'),'Alt+KeyA')
 assert.equal(readScreenshotShortcut({getItem(){throw Error('blocked')}},'alice'),'Alt+KeyA')
})

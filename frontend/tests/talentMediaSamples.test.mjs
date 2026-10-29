import test from 'node:test'
import assert from 'node:assert/strict'
import {sampleIsVideo,validSample,maxSampleBytes} from '../src/utils/talentMediaSamples.js'

test('音视频样音按扩展名验证，接受系统未识别MIME的常见格式',()=>{
  assert.equal(validSample({name:'样音.FLAC',size:100,type:''}),true)
  assert.equal(validSample({name:'样音.mkv',size:100,type:'application/octet-stream'}),true)
  assert.equal(sampleIsVideo('样音.MOV'),true)
  assert.equal(sampleIsVideo('样音.mp3'),false)
  for(const file of [{name:'a.exe',size:1},{name:'a.mp3',size:0},{name:'a.mp4',size:maxSampleBytes+1}])assert.equal(validSample(file),false)
})

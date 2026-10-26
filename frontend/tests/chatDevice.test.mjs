import test from 'node:test'
import assert from 'node:assert/strict'
import { chatClientType } from '../src/utils/chatDevice.js'

test('手机和平板不会被标为电脑，iPad 桌面 UA 也能区分', () => {
  assert.equal(chatClientType({ userAgent: 'Mozilla/5.0 Windows NT 10.0', platform: 'Win32', maxTouchPoints: 10 }), 'desktop')
  assert.equal(chatClientType({ userAgent: 'Mozilla/5.0 Macintosh', platform: 'MacIntel', maxTouchPoints: 0 }), 'desktop')
  assert.equal(chatClientType({ userAgent: 'Mozilla/5.0 Macintosh', platform: 'MacIntel', maxTouchPoints: 5 }), 'mobile')
  assert.equal(chatClientType({ userAgent: 'Mozilla/5.0 Android Tablet' }), 'mobile')
  assert.equal(chatClientType({ userAgent: 'Mozilla/5.0 iPhone' }), 'mobile')
  assert.equal(chatClientType({ userAgentData: { mobile: true }, userAgent: 'Unknown' }), 'mobile')
})

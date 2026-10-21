import { newFolderId } from './annotationMaterialFolders.js'

const channel = 'xinshi-office-save-v1'
export function installOfficeSaveShortcut({ getFrame, getOrigin, onSave }) {
  let nonce = newFolderId(), disposed = false
  function connect() {
    const frame = getFrame(), origin = getOrigin()
    if (frame?.contentWindow && origin) frame.contentWindow.postMessage({ channel, type: 'connect', nonce }, origin)
  }
  function message(event) {
    const frame = getFrame(), origin = getOrigin()
    if (disposed || !origin || !frame || event.source !== frame.contentWindow || event.origin !== origin || event.data?.channel !== channel) return
    if (event.data.type === 'ready') connect()
    else if (event.data.type === 'save' && event.data.nonce === nonce) onSave()
  }
  function keydown(event) {
    if (event.isComposing || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== 's') return
    event.preventDefault()
    if (!event.repeat) onSave()
  }
  window.addEventListener('message', message)
  window.addEventListener('keydown', keydown, true)
  return {
    connect,
    reset() { nonce = newFolderId() },
    dispose() { disposed = true; window.removeEventListener('message', message); window.removeEventListener('keydown', keydown, true) },
  }
}

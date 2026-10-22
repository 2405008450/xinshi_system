const pending=new Map()
export function registerScreenshotUpload(element,promise){pending.set(element,promise);promise.finally(()=>{if(pending.get(element)===promise)pending.delete(element)})}
export async function waitForScreenshotUploads(container){return (await Promise.all([...pending].filter(([element])=>container?.contains(element)).map(([,promise])=>promise))).every(Boolean)}

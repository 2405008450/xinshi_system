export function drawScreenshotMark(context, mark, makeCanvas = () => document.createElement('canvas')) {
  const { type, start, end = start, color = '#ef4444', size = 4 } = mark
  const x = Math.min(start.x, end.x), y = Math.min(start.y, end.y)
  const width = Math.abs(end.x - start.x), height = Math.abs(end.y - start.y)
  context.save(); context.strokeStyle = color; context.fillStyle = color; context.lineWidth = size; context.lineCap = 'round'; context.lineJoin = 'round'
  context.beginPath()
  if (type === 'rectangle') context.strokeRect(x, y, width, height)
  else if (type === 'ellipse') { context.ellipse(x + width / 2, y + height / 2, width / 2, height / 2, 0, 0, Math.PI * 2); context.stroke() }
  else if (type === 'pen') {
    const points = mark.points || [start, end]
    context.moveTo(start.x, start.y); points.forEach(point => context.lineTo(point.x, point.y)); context.stroke()
  } else if (type === 'arrow') {
    const angle = Math.atan2(end.y - start.y, end.x - start.x), length = size * 4
    context.moveTo(start.x, start.y); context.lineTo(end.x, end.y)
    context.moveTo(end.x - length * Math.cos(angle - Math.PI / 6), end.y - length * Math.sin(angle - Math.PI / 6))
    context.lineTo(end.x, end.y); context.lineTo(end.x - length * Math.cos(angle + Math.PI / 6), end.y - length * Math.sin(angle + Math.PI / 6)); context.stroke()
  } else if (type === 'text' || type === 'emoji') {
    const fontSize = type === 'emoji' ? size * 12 : size * 7
    context.font = `${fontSize}px sans-serif`; context.textBaseline = 'top'
    String(mark.text || '').split('\n').forEach((line, index) => context.fillText(line, start.x, start.y + index * fontSize * 1.25))
  } else if (type === 'mosaic' && width >= 1 && height >= 1) {
    const temp = makeCanvas(), block = size * 4
    temp.width = Math.max(1, Math.ceil(width / block)); temp.height = Math.max(1, Math.ceil(height / block))
    temp.getContext('2d').drawImage(context.canvas, x, y, width, height, 0, 0, temp.width, temp.height)
    context.imageSmoothingEnabled = false; context.drawImage(temp, 0, 0, temp.width, temp.height, x, y, width, height)
  }
  context.restore()
}

export function canvasPoint(clientX, clientY, rect, width, height) {
  return {
    x: Math.max(0, Math.min(width, (clientX - rect.left) * width / rect.width)),
    y: Math.max(0, Math.min(height, (clientY - rect.top) * height / rect.height)),
  }
}

export function createHistory() {
  const past = [], future = []
  return {
    get items() { return past },
    get canUndo() { return past.length > 0 },
    get canRedo() { return future.length > 0 },
    push(action) { past.push(action); future.length = 0 },
    undo() { if (past.length) future.push(past.pop()) },
    redo() { if (future.length) past.push(future.pop()) },
  }
}

export function paintStroke(context, stroke) {
  if (!stroke.points.length) return
  context.save()
  context.globalCompositeOperation = stroke.eraser ? 'destination-out' : 'source-over'
  context.strokeStyle = stroke.color
  context.fillStyle = stroke.color
  context.lineWidth = stroke.width
  context.lineCap = 'round'
  context.lineJoin = 'round'
  context.beginPath()
  if (stroke.points.length === 1) {
    context.arc(stroke.points[0].x, stroke.points[0].y, stroke.width / 2, 0, Math.PI * 2)
    context.fill()
  } else {
    context.moveTo(stroke.points[0].x, stroke.points[0].y)
    for (const point of stroke.points.slice(1)) context.lineTo(point.x, point.y)
    context.stroke()
  }
  context.restore()
}

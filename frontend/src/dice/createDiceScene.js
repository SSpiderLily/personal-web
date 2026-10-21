import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { DICE_SCALE, FACE_NORMALS, getFaceOrientation, getRollPose } from './diceMath.js'

// Three.js is MIT licensed. The motion is controlled so the backend owns the result.
export function createDiceScene(canvas, { onAvailabilityChange = () => {} } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.35
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-1.75, 1.75, 2.02, -1.67, .1, 30)
  camera.position.set(3.4, 4.5, 7)
  camera.lookAt(0, .7, 0)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x9da58c, 2.8))
  const light = new THREE.DirectionalLight(0xffffff, 4.5)
  light.position.set(-3, 7, 5)
  scene.add(light)
  const fill = new THREE.DirectionalLight(0xfff2da, 1.5)
  fill.position.set(5, 2, -4)
  scene.add(fill)

  const die = new THREE.Group()
  die.scale.setScalar(DICE_SCALE)
  die.position.y = .5 * DICE_SCALE - .5
  die.quaternion.copy(getFaceOrientation(1))
  scene.add(die)
  const material = new THREE.MeshPhysicalMaterial({
    color: 0xfff9ea, roughness: .24, metalness: 0, clearcoat: .65, clearcoatRoughness: .2,
  })
  die.add(new THREE.Mesh(new RoundedBoxGeometry(1, 1, 1, 5, .105), material))
  const pipGeometry = new THREE.SphereGeometry(.073, 24, 12)
  const pipMaterial = new THREE.MeshStandardMaterial({ color: 0x34482b, roughness: .5, metalness: .05 })
  const pips = {
    1: [[0, 0]], 2: [[-1, 1], [1, -1]], 3: [[-1, 1], [0, 0], [1, -1]],
    4: [[-1, 1], [1, 1], [-1, -1], [1, -1]],
    5: [[-1, 1], [1, 1], [0, 0], [-1, -1], [1, -1]],
    6: [[-1, 1], [1, 1], [-1, 0], [1, 0], [-1, -1], [1, -1]],
  }
  for (const [value, normal] of Object.entries(FACE_NORMALS)) {
    const face = new THREE.Group()
    face.position.set(...normal).multiplyScalar(.501)
    face.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(...normal))
    for (const [x, y] of pips[value]) {
      const pip = new THREE.Mesh(pipGeometry, pipMaterial)
      pip.scale.z = .16
      pip.position.set(x * .228, y * .228, 0)
      face.add(pip)
    }
    die.add(face)
  }

  const textureCanvas = document.createElement('canvas')
  textureCanvas.width = textureCanvas.height = 128
  const context = textureCanvas.getContext('2d')
  const gradient = context.createRadialGradient(64, 64, 2, 64, 64, 63)
  gradient.addColorStop(0, 'rgba(50,64,37,.35)')
  gradient.addColorStop(.45, 'rgba(50,64,37,.17)')
  gradient.addColorStop(1, 'rgba(50,64,37,0)')
  context.fillStyle = gradient
  context.fillRect(0, 0, 128, 128)
  const shadowTexture = new THREE.CanvasTexture(textureCanvas)
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(2.15, 2.15),
    new THREE.MeshBasicMaterial({ map: shadowTexture, transparent: true, depthWrite: false }))
  shadow.rotation.x = -Math.PI / 2
  shadow.position.y = -.508
  shadow.scale.setScalar(DICE_SCALE)
  scene.add(shadow)

  let disposed = false
  let contextAvailable = true
  let frameId = 0
  let cancelRoll
  const render = () => { if (!disposed && contextAvailable) renderer.render(scene, camera) }
  const resize = () => {
    const { width, height } = canvas.getBoundingClientRect()
    if (!width || !height || disposed) return
    renderer.setSize(width, height, false)
    const halfWidth = 3.69 * width / height / 2
    camera.left = -halfWidth
    camera.right = halfWidth
    camera.updateProjectionMatrix()
    render()
  }
  const observer = new ResizeObserver(resize)
  observer.observe(canvas)
  resize()

  function rollTo(value, { reducedMotion = false } = {}) {
    const target = getFaceOrientation(value)
    if (disposed || !contextAvailable) return Promise.reject(new DOMException('Scene unavailable', 'AbortError'))
    if (reducedMotion) {
      die.quaternion.copy(target)
      die.position.set(0, .5 * DICE_SCALE - .5, 0)
      shadow.scale.setScalar(DICE_SCALE)
      shadow.material.opacity = 1
      render()
      return Promise.resolve()
    }
    const start = die.quaternion.clone()
    const began = performance.now()
    return new Promise((resolve, reject) => {
      cancelRoll = () => reject(new DOMException('Scene disposed', 'AbortError'))
      function frame(now) {
        if (disposed) return
        const t = Math.min(1, (now - began) / 2650)
        const pose = getRollPose(start, value, t)
        die.quaternion.copy(pose.quaternion)
        die.position.copy(pose.position)
        shadow.scale.setScalar(DICE_SCALE * (1 + pose.lift * .35))
        shadow.material.opacity = 1 - pose.lift * .35
        render()
        if (t < 1) frameId = requestAnimationFrame(frame)
        else { cancelRoll = undefined; resolve() }
      }
      frameId = requestAnimationFrame(frame)
    })
  }

  function contextLost(event) {
    event.preventDefault()
    if (disposed) return
    contextAvailable = false
    cancelAnimationFrame(frameId)
    cancelRoll?.()
    cancelRoll = undefined
    onAvailabilityChange(false)
  }
  function contextRestored() {
    if (disposed) return
    contextAvailable = true
    // Vue synchronizes the latest backend result before making the canvas visible.
    onAvailabilityChange(true)
    render()
  }
  canvas.addEventListener('webglcontextlost', contextLost)
  canvas.addEventListener('webglcontextrestored', contextRestored)

  function dispose() {
    if (disposed) return
    disposed = true
    cancelAnimationFrame(frameId)
    cancelRoll?.()
    observer.disconnect()
    canvas.removeEventListener('webglcontextlost', contextLost)
    canvas.removeEventListener('webglcontextrestored', contextRestored)
    const geometries = new Set()
    const materials = new Set()
    scene.traverse(object => {
      if (object.geometry) geometries.add(object.geometry)
      if (object.material) materials.add(object.material)
    })
    for (const geometry of geometries) geometry.dispose()
    for (const material of materials) material.dispose()
    shadowTexture.dispose()
    renderer.dispose()
    renderer.forceContextLoss()
  }
  return { rollTo, dispose }
}

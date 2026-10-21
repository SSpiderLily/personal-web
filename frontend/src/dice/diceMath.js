import { Euler, Quaternion, Vector3 } from 'three'

export const DICE_SCALE = .5
export const FACE_NORMALS = Object.freeze({
  1: [0, 1, 0], 6: [0, -1, 0], 2: [0, 0, 1],
  5: [0, 0, -1], 3: [1, 0, 0], 4: [-1, 0, 0],
})
const up = new Vector3(0, 1, 0)

export function getFaceOrientation(value) {
  if (!Number.isInteger(value) || value < 1 || value > 6) throw new RangeError('Invalid dice value')
  return new Quaternion().setFromAxisAngle(up, -.28).multiply(
    new Quaternion().setFromUnitVectors(new Vector3(...FACE_NORMALS[value]), up),
  )
}

export function getTopFace(quaternion) {
  return Number(Object.keys(FACE_NORMALS).reduce((best, value) =>
    new Vector3(...FACE_NORMALS[value]).applyQuaternion(quaternion).y >
    new Vector3(...FACE_NORMALS[best]).applyQuaternion(quaternion).y ? value : best,
  ))
}

export function getRollPose(startQuaternion, value, progress) {
  const t = Math.max(0, Math.min(1, progress))
  const start = new Euler().setFromQuaternion(startQuaternion, 'XYZ')
  const end = new Euler().setFromQuaternion(getFaceOrientation(value), 'XYZ')
  const eased = 1 - (1 - t) ** 3
  const rotation = new Euler(
    start.x + (end.x + Math.PI * 6 - start.x) * eased,
    start.y + (end.y + Math.PI * 4 - start.y) * eased,
    start.z + (end.z + Math.PI * 4 - start.z) * eased,
  )
  const quaternion = new Quaternion().setFromEuler(rotation)
  const normal = up.clone().applyQuaternion(quaternion.clone().invert())
  // Support of a rounded cube: inner half-edge .395, rounding radius .105.
  const support = .395 * (Math.abs(normal.x) + Math.abs(normal.y) + Math.abs(normal.z)) + .105
  const rebound = (t - .48) / .52
  const lift = t < .48 ? Math.sin(Math.PI * t / .48) * 1.38
    : Math.abs(Math.sin(rebound * Math.PI * 3)) * (1 - rebound) ** 2 * .32
  return {
    quaternion,
    position: new Vector3(Math.sin(t * Math.PI) * .17 * DICE_SCALE, (support + lift) * DICE_SCALE - .5, 0),
    lift,
  }
}

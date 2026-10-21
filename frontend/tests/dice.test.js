import test from 'node:test'
import assert from 'node:assert/strict'
import { Quaternion, Vector3 } from 'three'
import { DICE_SCALE, FACE_NORMALS, getFaceOrientation, getRollPose, getTopFace } from '../src/dice/diceMath.js'
import { requestDiceValue } from '../src/dice/requestDiceValue.js'

test('all six backend values end with the matching face on top', () => {
  for (let value=1; value<=6; value++) {
    const orientation=getFaceOrientation(value)
    assert.ok(new Vector3(...FACE_NORMALS[value]).applyQuaternion(orientation).distanceTo(new Vector3(0,1,0))<1e-10)
    assert.equal(getTopFace(orientation),value)
    const pose=getRollPose(getFaceOrientation(7-value),value,1)
    assert.equal(getTopFace(pose.quaternion),value)
    assert.ok(Math.abs(pose.position.y-(-.5+.5*DICE_SCALE))<1e-10)
  }
})
test('dice edge is half prototype size and every face preserves opposite totals of seven', () => {
  assert.equal(DICE_SCALE,.5)
  for(let value=1;value<=6;value++) assert.ok(new Vector3(...FACE_NORMALS[value]).add(new Vector3(...FACE_NORMALS[7-value])).length()<1e-10)
})
test('roll starts at current rotation, lifts, and never intersects its ground', () => {
  const start=getFaceOrientation(4)
  assert.ok(getRollPose(start,2,0).quaternion.angleTo(start)<1e-7)
  assert.ok(getRollPose(start,2,.24).position.y>.3)
  for(let i=0;i<=100;i++){
    const pose=getRollPose(start,2,i/100)
    const up=new Vector3(0,1,0).applyQuaternion(pose.quaternion.clone().invert())
    const extent=(.395*(Math.abs(up.x)+Math.abs(up.y)+Math.abs(up.z))+.105)*DICE_SCALE
    assert.ok(pose.position.y-extent>=-.50000001)
  }
})
test('invalid target faces are rejected', () => {
  for(const value of [0,7,2.5,'2',null]) assert.throws(()=>getFaceOrientation(value),RangeError)
})
test('requests POST and returns only the validated backend value', async () => {
  let calls=0
  const value=await requestDiceValue({fetchImpl:async(url,options)=>{
    calls++;assert.equal(url,'/api/dice/roll');assert.equal(options.method,'POST');assert.ok(options.signal instanceof AbortSignal)
    return {ok:true,json:async()=>({value:6})}
  }})
  assert.equal(value,6);assert.equal(calls,1)
})
test('HTTP, network and invalid result failures never create a fallback value', async () => {
  await assert.rejects(requestDiceValue({fetchImpl:async()=>({ok:false})}))
  await assert.rejects(requestDiceValue({fetchImpl:async()=>{throw Error('offline')}}))
  for(const value of [0,7,1.5,'3',undefined]) await assert.rejects(requestDiceValue({fetchImpl:async()=>({ok:true,json:async()=>({value})})}))
})
test('cancelled requests do not publish a late result', async () => {
  const controller=new AbortController()
  await assert.rejects(requestDiceValue({signal:controller.signal,fetchImpl:async()=>({ok:true,json:async()=>{controller.abort();return {value:2}}})}),{name:'AbortError'})
})

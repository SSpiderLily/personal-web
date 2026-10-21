<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { requestDiceValue } from '../dice/requestDiceValue.js'

const canvas = ref(null)
const ready = ref(false)
const rolling = ref(false)
const value = ref(null)
const error = ref('')
const message = ref('点一下，试试手气')
const faces = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']
let scene
let controller
let disposed = false

onMounted(async () => {
  try {
    const { createDiceScene } = await import('../dice/createDiceScene.js')
    if (disposed) return
    scene = createDiceScene(canvas.value, {
      onAvailabilityChange(available) {
        if (disposed) return
        if (available) scene?.rollTo(value.value ?? 1, { reducedMotion: true })
        ready.value = available
      },
    })
    // The backend may already have answered while the 3D module was loading.
    scene.rollTo(value.value ?? 1, { reducedMotion: true })
    ready.value = true
  } catch {
    // A non-WebGL device can still roll using the backend and a simple dice face.
    ready.value = false
  }
})

async function roll() {
  if (rolling.value || disposed) return
  rolling.value = true
  error.value = ''
  message.value = '正在获取点数…'
  controller = new AbortController()
  try {
    const result = await requestDiceValue({ signal: controller.signal })
    if (disposed) return
    message.value = '骰子滚动中…'
    if (scene && ready.value) await scene.rollTo(result, { reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches })
    if (disposed) return
    value.value = result
    message.value = `${result} 点 · 再来一次？`
  } catch {
    if (!disposed) error.value = '没掷成功，点一下重试'
  } finally {
    if (!disposed) rolling.value = false
  }
}

onBeforeUnmount(() => {
  disposed = true
  controller?.abort()
  scene?.dispose()
})
</script>

<template>
  <div class="dice-toy" :class="{ 'has-result': value !== null }" aria-label="骰子小玩具">
    <canvas ref="canvas" class="dice-canvas" :class="{ 'is-ready': ready }" aria-hidden="true"></canvas>
    <button class="dice-trigger" :disabled="rolling" :aria-label="rolling ? '正在掷骰子' : '掷骰子'"
      aria-describedby="dice-result" title="点一下，试试手气" @click="roll">
      <span v-if="!ready" class="dice-fallback" aria-hidden="true">{{ faces[(value ?? 1) - 1] }}</span>
    </button>
    <span class="dice-caption" :class="{ 'has-error': error }" aria-hidden="true">{{ rolling ? '…' : error ? '重试' : value ? `${value} 点` : '掷骰子' }}</span>
    <p id="dice-result" class="sr-only" role="status" aria-live="polite">{{ error || message }}</p>
  </div>
</template>

<style scoped>
.dice-toy { position: fixed; left: -64px; bottom: max(14px, env(safe-area-inset-bottom)); width: 180px; height: 210px; z-index: 10; pointer-events: none; }
.dice-canvas { position: absolute; top: 0; left: 0; display: block; width: 180px; height: 190px; opacity: 0; }
.dice-canvas.is-ready { opacity: 1; }
.dice-trigger { position: absolute; left: 68px; bottom: 28px; width: 44px; height: 64px; border: 0; padding: 0; border-radius: 18px; background: transparent; pointer-events: auto; cursor: pointer; touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
.dice-trigger:focus-visible { outline: 2px solid #6d845b; outline-offset: 3px; }
.dice-trigger:disabled { cursor: wait; }
.dice-fallback { display: grid; place-items: center; width: 100%; height: 100%; color: #405e34; font-family: 'Apple Symbols', 'Segoe UI Symbol', sans-serif; font-size: 40px; }
.dice-caption { position: absolute; bottom: 0; left: 68px; width: 44px; margin: 0; border-radius: 18px; padding: 6px 3px; background: #f7f7f2d9; color: #6d7e60; text-align: center; font-size: 10px; line-height: 1.5; backdrop-filter: blur(5px); }
.has-result .dice-caption { color: #405e34; }
.dice-caption.has-error { color: #9a4b32; }
@media (max-width: 820px) {
  .dice-toy { left: -52px; bottom: max(9px, env(safe-area-inset-bottom)); width: 156px; height: 190px; }
  .dice-canvas { width: 156px; height: 170px; }
  .dice-trigger { left: 56px; bottom: 22px; }
  .dice-caption { left: 56px; font-size: 9px; }
}
</style>

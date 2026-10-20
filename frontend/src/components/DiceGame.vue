<script setup>
import { onBeforeUnmount, ref } from 'vue'

const value = ref(null)
const rolling = ref(false)
const error = ref('')
const faces = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']
let controller

async function roll() {
  if (rolling.value) return
  rolling.value = true
  error.value = ''
  value.value = null
  controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    // A short minimum duration keeps the animation visible even for local requests.
    const [response] = await Promise.all([
      fetch('/api/dice/roll', { method: 'POST', signal: controller.signal }),
      new Promise(resolve => setTimeout(resolve, 450)),
    ])
    if (!response.ok) throw new Error('Roll failed')
    const result = await response.json()
    if (!Number.isInteger(result.value) || result.value < 1 || result.value > 6) {
      throw new Error('Invalid dice result')
    }
    value.value = result.value
  } catch {
    error.value = '这次没有掷成功，请稍后点击骰子重试。'
  } finally {
    clearTimeout(timeout)
    rolling.value = false
  }
}

onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="dice-game" aria-labelledby="dice-heading">
    <div>
      <p class="eyebrow">TAKE A BREAK</p>
      <h2 id="dice-heading">今天的手气如何？</h2>
      <p class="dice-hint">给忙碌按个暂停，掷出今天的小幸运。</p>
    </div>
    <div class="dice-play">
      <button class="dice" :class="{ rolling }" :disabled="rolling"
        :aria-label="rolling ? '正在掷骰子' : '掷骰子'" @click="roll">
        <span aria-hidden="true">{{ faces[(value ?? 1) - 1] }}</span>
      </button>
      <p class="dice-result" role="status" aria-live="polite">
        {{ rolling ? '骰子滚动中…' : error || (value ? `掷出了 ${value} 点！再试一次？` : '点击开始') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.dice-game { display: flex; flex-direction: column; align-items: stretch; gap: 26px; padding: 28px 23px 22px; margin: 0; background: #edf1e5; border: 1px solid #dce3d1; border-radius: 14px; }
.eyebrow { font-size: 9px; margin-bottom: 17px; letter-spacing: 1.8px; color: #869374; }
h2 { font-size: 19px; margin: 0 0 12px; font-weight: 600; letter-spacing: -.5px; }
.dice-hint { color: #87927b; font-size: 11px; line-height: 1.9; margin: 0; max-width: 185px; }
.dice-play { text-align: center; padding: 8px 0 0; }
.dice { display: inline-grid; place-items: center; width: 86px; height: 86px; padding: 0; border: 1px solid #dbe2ce; border-radius: 18px; background: #fffef8; color: #4c6841; box-shadow: 0 6px 0 #dbe2ce; transition: transform .15s; cursor: pointer; }
.dice span { font-size: 68px; line-height: 1; font-family: 'Apple Symbols', 'Segoe UI Symbol', sans-serif; }
.dice:hover:not(:disabled) { transform: translateY(-3px); }
.dice:disabled { cursor: wait; }
.dice-result { min-height: 36px; margin: 23px 0 0; font-size: 11px; line-height: 1.7; color: #748366; }
.rolling { animation: tumble .3s infinite ease-in-out; }
@keyframes tumble { 0%, 100% { transform: rotate(-14deg); } 50% { transform: rotate(14deg) translateY(-6px); } }
@media (prefers-reduced-motion: reduce) { .rolling { animation: none; } .dice { transition: none; } }
@media (min-width: 541px) and (max-width: 820px) { .dice-game { flex-direction: row; align-items: center; justify-content: space-between; } .dice-play { min-width: 180px; } }
</style>

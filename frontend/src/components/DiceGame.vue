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
      <p class="eyebrow">TAKE A BREAK / 休息一下</p>
      <h2 id="dice-heading">今天的手气如何？</h2>
      <p class="dice-hint">点击骰子，看看这次会掷出几点。</p>
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
.dice-game { display: flex; align-items: center; justify-content: space-between; gap: 28px; padding: 32px; margin-bottom: 64px; background: #edf2e8; border: 1px solid #d6ddd2; border-radius: 12px; }
.eyebrow { margin-bottom: 16px; }
h2 { font-size: 24px; margin: 0 0 12px; }
.dice-hint { color: #646e67; font-size: 14px; line-height: 1.8; }
.dice-play { text-align: center; flex: 0 1 300px; }
.dice { display: inline-grid; place-items: center; width: 96px; height: 96px; padding: 0; border: 1px solid #d6ddd2; border-radius: 18px; background: #fff; color: #375c43; box-shadow: 0 6px 0 #d6ddd2; transition: transform .15s; }
.dice span { font-size: 76px; line-height: 1; font-family: 'Apple Symbols', 'Segoe UI Symbol', sans-serif; }
.dice:hover:not(:disabled) { transform: translateY(-3px); }
.dice:disabled { cursor: wait; }
.dice-result { min-height: 44px; margin: 20px 0 0; font-size: 14px; line-height: 1.6; color: #375c43; }
.rolling { animation: tumble .3s infinite ease-in-out; }
@keyframes tumble { 0%, 100% { transform: rotate(-14deg); } 50% { transform: rotate(14deg) translateY(-6px); } }
@media (prefers-reduced-motion: reduce) { .rolling { animation: none; } .dice { transition: none; } }
@media (max-width: 600px) { .dice-game { flex-direction: column; align-items: stretch; padding: 24px; } .dice-play { flex-basis: auto; } }
</style>

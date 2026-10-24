<script setup>
// These remain visual placeholders. The caller supplies sorted visible items.
defineProps({ items: { type: Array, default: () => [] } })
const icons = Object.fromEntries([
  'M7 3h10v18H7zM10 7h4M10 11h1m2 0h1m-4 4h1m2 0h1m-4 3h4',
  'M12 8v5l3 2M9 2h6M12 2v3M18 5l2 2',
  'M8 8 3 12l5 4m8-8 5 4-5 4M14 4l-4 16',
  'M5 5h14v14H5zM9 9h6v6H9zM9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3',
  'M8 3H4v18h16V7l-4-4H8zM8 11h8M8 15h8M8 18h5M15 3v5h5',
  'm12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.4l6.1-.9z',
  'M8 7V4h12v12h-3M4 8h12v12H4z',
  'm15 15 6 6M7 10h6M10 7v6',
  'M5 12h14M12 5v14',
].map((path, index) => [`grid_${String(index + 1).padStart(2, '0')}`, { path, number: index + 1 }]))
</script>

<template>
  <ul class="tools-grid" aria-label="工具占位，尚未开放">
    <li v-for="item in items" :key="item.tool_key" class="tool-cell" :aria-label="`工具占位 ${icons[item.tool_key]?.number}，尚未开放`" :title="`工具占位 ${icons[item.tool_key]?.number} · 尚未开放`">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle v-if="item.tool_key === 'grid_02'" cx="12" cy="13" r="8" />
        <circle v-if="item.tool_key === 'grid_08'" cx="10" cy="10" r="6" />
        <circle v-if="item.tool_key === 'grid_09'" cx="12" cy="12" r="10" />
        <path :d="icons[item.tool_key]?.path" />
      </svg>
    </li>
  </ul>
  <p class="tool-note"><span aria-hidden="true"></span>给一些小想法，留一点位置。</p>
</template>

<style scoped>
.tools-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; list-style: none; padding: 0; margin: 0; }
.tool-cell { aspect-ratio: 1; position: relative; display: flex; align-items: center; justify-content: center; border: 1px solid #e0e5d8; border-radius: 15px; background: #fffefa; color: #839775; }
.tool-cell:nth-child(3n + 2) { background: #edf1e6; }
.tool-cell:nth-child(3n) { background: #f0f0e6; }
.tool-cell svg { width: 27px; height: 27px; stroke-width: 1.35; }
.tool-cell::after { content: ''; position: absolute; bottom: 12px; width: 13px; height: 2px; border-radius: 2px; background: #cbd4be; }
.tool-note { display: flex; align-items: center; gap: 9px; color: #8d9883; font-size: 10px; margin: 20px 0 0; }
.tool-note span { width: 18px; height: 1px; background: #bcc9b0; }
@media (max-width: 1080px) { .tools-grid { gap: 8px; } .tool-cell { border-radius: 12px; } }
@media (max-width: 820px) { .tools-grid { max-width: 400px; gap: 12px; } .tool-cell svg { width: 32px; height: 32px; } }
@media (max-width: 540px) { .tools-grid { max-width: none; } .tool-cell { max-height: 126px; } }
</style>

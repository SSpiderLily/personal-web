import { createApp } from 'vue'

// Native navigation keeps the public page and admin styles/components separate.
const isAdmin = /^\/admin(?:\/|$)/.test(window.location.pathname)
const { default: App } = isAdmin
  ? await import('./admin/AdminApp.vue')
  : await import('./App.vue')
if (!isAdmin) await import('./style.css')

createApp(App).mount('#app')

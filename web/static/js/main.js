import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import Home from './views/Home.vue'
import Doctor from './views/Doctor.vue'

const pinia = createPinia()
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/home', component: Home },
    { path: '/doctor', component: Doctor },
    { path: '/', redirect: '/home' },
    { path: '/:pathMatch(.*)*', redirect: '/home' }
  ]
})

const app = createApp({})
app.use(router)
app.use(pinia)
app.mount('#app')
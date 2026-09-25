import { defineStore } from 'pinia'
import { ref } from 'vue'
import { request } from '../lib/api'

export const useSession = defineStore('session', () => {
  const loggedIn = ref(Boolean(uni.getStorageSync('fitmind.token')))
  const userId = ref<string>(uni.getStorageSync('fitmind.user') || '')
  async function startDevelopmentSession() {
    const result = await request<{ access_token: string; user_id: string }>('/api/v1/auth/dev-session', 'POST')
    uni.setStorageSync('fitmind.token', result.access_token)
    uni.setStorageSync('fitmind.user', result.user_id)
    userId.value = result.user_id
    loggedIn.value = true
  }
  function localKey(name: string) { return `fitmind.${userId.value}.${name}` }
  return { loggedIn, userId, startDevelopmentSession, localKey }
})

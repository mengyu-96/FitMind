import { defineStore } from 'pinia'
import { ref } from 'vue'
import { request } from '../lib/api'

export const useSession = defineStore('session', () => {
  const loggedIn = ref(Boolean(uni.getStorageSync('fitmind.token')))
  const userId = ref<string>(uni.getStorageSync('fitmind.user') || '')
  function acceptSession(result: { access_token: string; user_id: string }) {
    uni.setStorageSync('fitmind.token', result.access_token)
    uni.setStorageSync('fitmind.user', result.user_id)
    userId.value = result.user_id
    loggedIn.value = true
  }
  async function startDevelopmentSession() {
    const result = await request<{ access_token: string; user_id: string }>('/api/v1/auth/dev-session', 'POST')
    acceptSession(result)
  }
  function localKey(name: string) { return `fitmind.${userId.value}.${name}` }
  function clearSession() {
    uni.removeStorageSync('fitmind.token'); uni.removeStorageSync('fitmind.user')
    uni.removeStorageSync(localKey('conversation')); uni.removeStorageSync(localKey('pending-chat'))
    uni.removeStorageSync(localKey('pending-record'))
    userId.value = ''; loggedIn.value = false
  }
  async function logout() {
    try { await request('/api/v1/auth/session', 'DELETE') } finally { clearSession() }
  }
  uni.$on('fitmind-auth-expired', clearSession)
  return { loggedIn, userId, startDevelopmentSession, acceptSession, localKey, clearSession, logout }
})

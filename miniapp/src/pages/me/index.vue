<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { errorMessage, request, type Receipt } from '../../lib/api'
import { operationId, type FitnessObject } from '../../lib/api'
import { useSession } from '../../stores/session'

const session = useSession()
const error = ref('')
const busy = ref(false)
const operations = ref<Receipt[]>([])
const preference = ref('')
const preferenceObject = ref<FitnessObject | null>(null)
async function load() {
  if (!session.loggedIn) return
  try {
    operations.value = (await request<{ items: Receipt[] }>('/api/v1/operations')).items
    const items = (await request<{ items: FitnessObject[] }>('/api/v1/objects?limit=100')).items
    preferenceObject.value = items.find(item => item.kind === 'coaching_preference') || null
    preference.value = String(preferenceObject.value?.payload.text || '')
  }
  catch (e) { error.value = errorMessage(e) }
}
onShow(load)
async function start() {
  busy.value = true; error.value = ''
  try { await session.startDevelopmentSession(); await load() }
  catch (e) { error.value = errorMessage(e) }
  finally { busy.value = false }
}
function loginWechat() {
  uni.login({ provider: 'weixin', success(result) {
    if (!result.code) { error.value = '微信未返回登录凭证。'; return }
    busy.value = true
    request<{ access_token: string; user_id: string }>('/api/v1/auth/wechat-login?code=' + encodeURIComponent(result.code), 'POST')
      .then(session.acceptSession).then(load).catch(e => { error.value = errorMessage(e) })
      .finally(() => { busy.value = false })
  }, fail: () => { error.value = '当前开发工具未启用微信登录。' } })
}
async function savePreference() {
  busy.value = true; error.value = ''
  const id = operationId()
  const change = preferenceObject.value
    ? { action: 'replace', object_id: preferenceObject.value.id,
        expected_version: preferenceObject.value.version, payload: { ...preferenceObject.value.payload, text: preference.value } }
    : { action: 'create', kind: 'coaching_preference', payload: { text: preference.value } }
  try {
    await request('/api/v1/agent-actions/apply', 'POST', { operation_id: id, operations: [change] }, id)
    await load(); uni.showToast({ title: '偏好已保存', icon: 'success' })
  } catch (e) { error.value = errorMessage(e) }
  finally { busy.value = false }
}
async function exportData() {
  busy.value = true; error.value = ''
  try {
    const data = await request<Record<string, unknown>>('/api/v1/me/export')
    const contents = JSON.stringify(data, null, 2)
    uni.setClipboardData({ data: contents, success: () => uni.showModal({ title: '导出内容已复制',
      content: 'FitMind 数据以 JSON 复制到剪贴板。请粘贴到你自己的安全位置保存。', showCancel: false }) })
  } catch (e) { error.value = errorMessage(e) }
  finally { busy.value = false }
}
function deleteAccount() {
  uni.showModal({ title: '永久删除账户数据？',
    content: '将删除当前账户的记录、计划、对话和操作历史。此操作无法撤销。',
    confirmText: '永久删除', confirmColor: '#a43f31', success: async result => {
      if (!result.confirm) return
      busy.value = true; error.value = ''
      try {
        await request('/api/v1/me?confirmation=' + encodeURIComponent('永久删除我的FitMind数据'), 'DELETE')
        session.clearSession(); operations.value = []; preference.value = ''; preferenceObject.value = null
        uni.showToast({ title: '数据已删除', icon: 'success' })
      } catch (e) { error.value = errorMessage(e) }
      finally { busy.value = false }
    } })
}
</script>

<template>
  <view class="page">
    <view class="eyebrow">YOUR SPACE</view><view class="title">按自己的方式来</view>
    <view class="subtitle">记录属于你，是否继续聊也由你决定。</view>
    <view class="card">
      <view class="tag">开发联调 · G1</view>
      <view class="body" style="margin-top: 20rpx">当前使用开发会话，尚未接入正式微信登录。请使用测试内容。</view>
      <view class="muted" style="margin-top: 16rpx">教练消息和相关上下文会发送到已配置的 DeepSeek 服务生成反馈。单独保存记录不调用模型。</view>
      <button v-if="!session.loggedIn" class="primary" style="margin-top: 26rpx" :loading="busy" :disabled="busy" @tap="start">了解并启用测试会话</button>
      <button v-if="!session.loggedIn" class="secondary" style="margin-top: 18rpx" @tap="loginWechat">使用微信登录</button>
      <view v-else class="muted" style="margin-top: 18rpx">测试会话已启用。本机保留会话凭据，请勿清除存储以免失去当前测试数据的访问入口。</view>
      <view v-if="error" class="error">{{ error }}</view>
    </view>
    <view v-if="session.loggedIn" class="card">
      <view class="label">教练交流偏好</view>
      <view class="muted">自由描述你希望怎样交流或安排训练。这些内容会作为你的自述供教练参考，不会自动扩大操作授权。</view>
      <textarea v-model="preference" maxlength="4000" placeholder="例如：先给简短建议；不固定哪天训练；我不确定时先问我。" />
      <button class="secondary" :loading="busy" :disabled="busy" @tap="savePreference">保存偏好</button>
    </view>
    <view class="card">
      <view class="label">交流与权限</view>
      <view class="body">仅在你发送消息时调用教练。离开后不推送，不积压催促。</view>
      <view class="muted" style="margin-top: 16rpx">持续自主调整尚未开放；数据导出和删除入口已可用。当前任务权限不会自动扩展成后台授权。</view>
    </view>
    <view class="subtitle" style="margin-top: 32rpx">最近操作</view>
    <view v-if="session.loggedIn" class="row">
      <button class="secondary" :disabled="busy" @tap="exportData">导出我的数据</button>
      <button class="secondary" :disabled="busy" @tap="deleteAccount">删除账户数据</button>
    </view>
    <view v-if="!operations.length" class="empty">还没有保存操作。</view>
    <view v-for="item in operations" :key="item.operation_id" class="card">
      <view class="body">已保存 {{ item.objects.length }} 条内容</view>
      <view v-for="object in item.objects" :key="object.id" class="muted">{{ object.kind }} · v{{ object.version }}</view>
      <view class="muted" style="margin-top: 12rpx">{{ item.operation_id }}</view>
    </view>
  </view>
</template>

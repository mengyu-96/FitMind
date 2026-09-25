<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { errorMessage, operationId, request, type Turn } from '../../lib/api'
import { useSession } from '../../stores/session'

const session = useSession()
const draft = ref('')
const turns = ref<Turn[]>([])
const busy = ref(false)
const error = ref('')
type Pending = { operation_id: string; text: string; intent: 'chat' | 'record' | 'task' }
const pending = ref<Pending | null>(null)
let conversationId = ''

async function load() {
  if (!session.loggedIn || busy.value) return
  pending.value = uni.getStorageSync(session.localKey('pending-chat')) || null
  conversationId = uni.getStorageSync(session.localKey('conversation')) || ''
  if (!conversationId) return
  try {
    turns.value = (await request<{ items: Turn[] }>(`/api/v1/conversations/${conversationId}/messages`)).items
    if (pending.value && turns.value.some(t => t.operation_id === pending.value?.operation_id)) {
      pending.value = null
      uni.removeStorageSync(session.localKey('pending-chat'))
    }
  } catch (e) { error.value = errorMessage(e) }
}
onShow(load) // Reading history never generates a greeting or starts a model run.

async function send(intent: 'chat' | 'record' | 'task') {
  if (busy.value || (!draft.value.trim() && !pending.value)) return
  busy.value = true
  error.value = ''
  try {
    if (!conversationId) {
      const result = await request<{ id: string }>('/api/v1/conversations', 'POST')
      conversationId = result.id
      uni.setStorageSync(session.localKey('conversation'), result.id)
    }
    if (!pending.value) {
      pending.value = { operation_id: operationId(), text: draft.value.trim(), intent }
      uni.setStorageSync(session.localKey('pending-chat'), pending.value)
    }
    const result = await request<Turn>(`/api/v1/conversations/${conversationId}/messages`, 'POST', pending.value, pending.value.operation_id)
    if (!turns.value.some(t => t.operation_id === result.operation_id)) turns.value.push(result)
    uni.removeStorageSync(session.localKey('pending-chat'))
    pending.value = null
    draft.value = ''
  } catch (e) { error.value = errorMessage(e) }
  finally { busy.value = false }
}
function goToMe() { uni.switchTab({ url: '/pages/me/index' }) }
</script>

<template>
  <view class="page">
    <view class="eyebrow">FITMIND / 每一步都有意义</view>
    <view class="title">从今天的感受说起</view>
    <view class="subtitle">不必准备完整的数据。一个想法、一段训练，或只是今天的状态，都可以聊聊。</view>
    <view v-if="!session.loggedIn" class="card">
      <view class="body">当前为开发联调版本，请先在“我的”启用测试会话。</view>
      <button class="primary" style="margin-top: 24rpx" @tap="goToMe">前往我的</button>
    </view>
    <template v-else>
      <view v-if="!turns.length" class="card">
        <view class="label">你可以这样开始</view>
        <view class="body">“今天练腿，很累。”<br />“我希望运动能坚持得轻松一点。”</view>
        <view class="muted" style="margin-top: 18rpx">想聊就发消息，想留下一条训练记录就点“发送并记录”。</view>
      </view>
      <view v-for="turn in turns" :key="turn.operation_id" class="card">
        <view class="label">我</view><view class="body">{{ turn.text }}</view>
        <view class="label" style="margin-top: 28rpx">FITMIND</view><view class="body">{{ turn.reply }}</view>
        <view v-for="receipt in turn.receipts" :key="receipt.operation_id" style="margin-top: 18rpx">
          <text class="tag">已保存 · 版本 {{ receipt.objects[0]?.version }}</text>
        </view>
        <view v-if="turn.status === 'partial'" class="muted">保存已完成，本轮教练反馈未完成。</view>
      </view>
      <view class="card">
        <textarea v-model="draft" :disabled="busy || !!pending" :maxlength="8000" placeholder="说说现在的想法……" />
        <view v-if="pending" class="muted">正在确认提交：{{ pending.text }}</view>
        <view v-if="error" class="error">{{ error }}</view>
        <view v-if="pending" class="row"><button class="primary" :disabled="busy" :loading="busy" @tap="send(pending.intent)">重试原提交</button></view>
        <view v-else class="row">
          <button class="secondary" :disabled="busy || !draft.trim()" @tap="send('record')">发送并记录</button>
          <button class="secondary" :disabled="busy || !draft.trim()" @tap="send('task')">交给教练处理</button>
          <button class="primary" :disabled="busy || !draft.trim()" :loading="busy" @tap="send('chat')">发送</button>
        </view>
        <view class="muted" style="margin-top: 20rpx">离开后不会主动推送。回来时可以接着聊。</view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ApiError, errorMessage, operationId, request, type FitnessObject, type Receipt } from '../../lib/api'
import { useSession } from '../../stores/session'

const session = useSession()
const items = ref<FitnessObject[]>([])
const draft = ref('')
const editing = ref<FitnessObject | null>(null)
const busy = ref(false)
const error = ref('')
type Change = { action: string; kind?: string; payload?: Record<string, unknown>; object_id?: string; expected_version?: number; restore_version?: number }
type Pending = { operation_id: string; operations: Change[] }
const pending = ref<Pending | null>(null)
const hasMore = ref(false)

async function load(append = false) {
  if (!session.loggedIn) return
  pending.value = uni.getStorageSync(session.localKey('pending-record')) || null
  try {
    const result = await request<{ items: FitnessObject[] }>(`/api/v1/objects?offset=${append ? items.value.length : 0}`)
    items.value = append ? [...items.value, ...result.items] : result.items
    hasMore.value = result.items.length === 50
  } catch (e) { error.value = errorMessage(e) }
}
onShow(() => { if (!busy.value) load() })

async function apply(operations: Change[]) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    if (!pending.value) {
      pending.value = { operation_id: operationId(), operations }
      uni.setStorageSync(session.localKey('pending-record'), pending.value)
    }
    await request<Receipt>('/api/v1/agent-actions/apply', 'POST', pending.value, pending.value.operation_id)
    pending.value = null
    uni.removeStorageSync(session.localKey('pending-record'))
    draft.value = ''; editing.value = null
    await load()
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    error.value = errorMessage(e)
    if (e instanceof ApiError && ['VERSION_CONFLICT', 'INVALID_INPUT', 'NOT_FOUND'].includes(e.code)) {
      // Definitive rejection: allow a fresh edit after reloading; retain draft text.
      pending.value = null
      uni.removeStorageSync(session.localKey('pending-record'))
      editing.value = null
      await load()
    }
  } finally { busy.value = false }
}
function save() {
  if (pending.value) return apply(pending.value.operations)
  if (!draft.value.trim()) return
  if (editing.value) {
    return apply([{ action: 'replace', object_id: editing.value.id, expected_version: editing.value.version,
      payload: { ...editing.value.payload, text: draft.value.trim() } }])
  }
  return apply([{ action: 'create', kind: 'activity', payload: { text: draft.value.trim(), activity_status: 'reported' } }])
}
function edit(item: FitnessObject) {
  editing.value = item; draft.value = String(item.payload.text || '')
  uni.pageScrollTo({ scrollTop: 0, duration: 200 })
}
function extra(item: FitnessObject) {
  return Object.entries(item.payload).filter(([key]) => !['text', 'activity_status'].includes(key))
    .map(([key, value]) => `${key}：${typeof value === 'object' ? JSON.stringify(value) : value}`).join('\n')
}
function undo(item: FitnessObject) {
  uni.showModal({ title: '恢复上一版本', content: '会生成一个新修订并保留版本历史。', success(result) {
    if (result.confirm) apply([{ action: 'undo', object_id: item.id, expected_version: item.version, restore_version: item.version - 1 }])
  } })
}
</script>

<template>
  <view class="page">
    <view class="eyebrow">YOUR PRACTICE</view><view class="title">记录自己的节奏</view>
    <view class="subtitle">一句话也值得留下。没有组数、重量或时间，也可以保存。</view>
    <view v-if="!session.loggedIn" class="empty">请先在“我的”启用测试会话。</view>
    <template v-else>
      <view class="card">
        <view class="label">{{ editing ? '更正这条记录 · v' + editing.version : '留下一条记录' }}</view>
        <textarea v-model="draft" :maxlength="8000" :disabled="busy || !!pending" placeholder="例如：今天散步了一会儿，心情轻松了些。" />
        <view v-if="error" class="error">{{ error }}</view>
        <view v-if="pending" class="muted">有一条提交待确认，重试会沿用原标识。</view>
        <view class="row">
          <button v-if="editing && !pending" class="secondary" :disabled="busy" @tap="editing = null; draft = ''">取消更正</button>
          <button class="primary" :loading="busy" :disabled="busy || (!draft.trim() && !pending)" @tap="save">{{ pending ? '重试原提交' : '保存记录' }}</button>
        </view>
      </view>
      <view class="card"><view class="label">计划</view><view class="muted">计划功能正在开发。现在可以先记录真实训练和想法。</view></view>
      <view class="subtitle" style="margin-top: 32rpx">已保存的内容</view>
      <view v-if="!items.length" class="empty">这里还没有记录。<br />从一小段经历开始就好。</view>
      <view v-for="item in items" :key="item.id" class="card">
        <view class="label">{{ item.kind === 'activity' ? '活动自述' : item.kind }} · v{{ item.version }}</view>
        <view class="body">{{ item.payload.text || '自由内容' }}</view>
        <view v-if="extra(item)" class="muted" style="margin-top: 16rpx">{{ extra(item) }}</view>
        <view class="row">
          <button class="secondary small" :disabled="busy || !!pending" @tap="edit(item)">补充 / 更正</button>
          <button v-if="item.version > 1" class="secondary small" :disabled="busy || !!pending" @tap="undo(item)">恢复上一版</button>
        </view>
      </view>
      <button v-if="hasMore" class="secondary" style="margin-top: 24rpx" @tap="load(true)">加载更多</button>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { errorMessage, operationId, request, type Turn } from '../../lib/api'
import { useSession } from '../../stores/session'
const session = useSession(); const draft = ref(''); const turns = ref<Turn[]>([]); const busy = ref(false); const error = ref('')
type Pending = { operation_id: string; text: string; intent: 'chat' | 'record' | 'task' }; const pending = ref<Pending | null>(null); let conversationId = ''
async function load() { if (!session.loggedIn || busy.value) return; pending.value = uni.getStorageSync(session.localKey('pending-chat')) || null; conversationId = uni.getStorageSync(session.localKey('conversation')) || ''; if (!conversationId) return; try { turns.value = (await request<{ items: Turn[] }>(`/api/v1/conversations/${conversationId}/messages`)).items; if (pending.value && turns.value.some(t => t.operation_id === pending.value?.operation_id)) { pending.value = null; uni.removeStorageSync(session.localKey('pending-chat')) } } catch (e) { error.value = errorMessage(e) } }
onShow(load)
async function send(intent: 'chat' | 'record' | 'task') { if (busy.value || (!draft.value.trim() && !pending.value)) return; busy.value = true; error.value = ''; try { if (!conversationId) { const result = await request<{ id: string }>('/api/v1/conversations', 'POST'); conversationId = result.id; uni.setStorageSync(session.localKey('conversation'), result.id) } if (!pending.value) { pending.value = { operation_id: operationId(), text: draft.value.trim(), intent }; uni.setStorageSync(session.localKey('pending-chat'), pending.value) } const result = await request<Turn>(`/api/v1/conversations/${conversationId}/messages`, 'POST', pending.value, pending.value.operation_id); if (!turns.value.some(t => t.operation_id === result.operation_id)) turns.value.push(result); uni.removeStorageSync(session.localKey('pending-chat')); pending.value = null; draft.value = '' } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
function goToMe() { uni.switchTab({ url: '/pages/me/index' }) }
</script>
<template><view class="page">
  <view class="eyebrow">FITMIND · 陪你练得更轻松</view><view class="title">今天感觉怎么样？</view><view class="subtitle">不用准备完整数据。告诉我刚刚发生了什么，或者你想解决什么问题。</view>
  <view v-if="!session.loggedIn" class="card"><view class="label">开始使用</view><view class="body">登录后可以保存训练记录、整理计划，并在下次回来时接着聊。</view><button class="primary" style="margin-top: 26rpx" @tap="goToMe">去登录</button></view>
  <template v-else>
    <view v-if="!turns.length" class="card"><view class="label">你可以这样说</view><view class="hint">“今天练腿有点累”<br />“帮我安排一个轻松的训练”<br />“我想知道怎么恢复得更好”</view><view class="muted" style="margin-top: 18rpx">不确定怎么问也没关系，我会先问一个最有帮助的问题。</view></view>
    <view v-for="turn in turns" :key="turn.operation_id" class="card"><view class="label">你说</view><view class="body">{{ turn.text }}</view><view class="label" style="margin-top: 24rpx">教练</view><view class="body">{{ turn.reply }}</view><view v-for="receipt in turn.receipts" :key="receipt.operation_id" class="tag" style="margin-top: 16rpx">已帮你保存</view><view v-if="turn.status === 'partial'" class="hint" style="margin-top: 16rpx">记录已经保存，教练回复暂时中断了。你可以稍后重试。</view></view>
    <view class="card"><view class="label">写下你现在的想法</view><textarea v-model="draft" :disabled="busy || !!pending" :maxlength="8000" placeholder="例如：今天走了很多路，腿有点酸……" /><view v-if="pending" class="hint">正在完成刚才的提交：{{ pending.text }}</view><view v-if="error" class="error">{{ error }}</view><view v-if="pending" class="row"><button class="primary" :disabled="busy" :loading="busy" @tap="send(pending.intent)">重试刚才的操作</button></view><template v-else><view class="row"><button class="secondary" :disabled="busy || !draft.trim()" @tap="send('record')">只保存记录</button><button class="primary" :disabled="busy || !draft.trim()" :loading="busy" @tap="send('chat')">和教练聊聊</button></view><button class="ghost" style="width: 100%; margin-top: 14rpx" :disabled="busy || !draft.trim()" @tap="send('task')">交给教练整理成计划</button></template><view class="muted" style="margin-top: 18rpx">你离开后不会收到催促消息，回来时可以从这里继续。</view></view>
  </template>
</view></template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { errorMessage, request, type Receipt } from '../../lib/api'
import { useSession } from '../../stores/session'

const session = useSession()
const error = ref('')
const busy = ref(false)
const operations = ref<Receipt[]>([])
async function load() {
  if (!session.loggedIn) return
  try { operations.value = (await request<{ items: Receipt[] }>('/api/v1/operations')).items }
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
    error.value = '微信登录接口已准备，需后端配置 AppSecret 后启用。'
  }, fail: () => { error.value = '当前开发工具未启用微信登录。' } })
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
    <view class="card">
      <view class="label">交流与权限</view>
      <view class="body">仅在你发送消息时调用教练。离开后不推送，不积压催促。</view>
      <view class="muted" style="margin-top: 16rpx">持续自主调整、数据导出和注销正在开发，尚未开放。后续版本会提供明确范围和撤销入口。</view>
    </view>
    <view class="subtitle" style="margin-top: 32rpx">最近操作</view>
    <view v-if="!operations.length" class="empty">还没有保存操作。</view>
    <view v-for="item in operations" :key="item.operation_id" class="card">
      <view class="body">已保存 {{ item.objects.length }} 条内容</view>
      <view v-for="object in item.objects" :key="object.id" class="muted">{{ object.kind }} · v{{ object.version }}</view>
      <view class="muted" style="margin-top: 12rpx">{{ item.operation_id }}</view>
    </view>
  </view>
</template>

<script setup lang="ts"></script>

<template><slot /></template>

<style>
page { background: #f7f8f5; color: #1e3028; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; font-size: 28rpx; }
view, text, button, textarea { box-sizing: border-box; }
.page { padding: 34rpx 28rpx 70rpx; }
.eyebrow { color: #6b8b78; font-size: 22rpx; letter-spacing: 3rpx; margin-bottom: 14rpx; font-weight: 600; }
.title { font-size: 48rpx; font-weight: 700; line-height: 1.3; letter-spacing: 1rpx; }
.subtitle { color: #718078; line-height: 1.8; margin-top: 14rpx; }
.card { background: #fff; border-radius: 26rpx; padding: 30rpx; margin-top: 24rpx; border: 1rpx solid #e5e9e2; box-shadow: 0 10rpx 30rpx rgba(39, 73, 58, .04); }
.label { font-size: 23rpx; color: #78877e; margin-bottom: 12rpx; }
.body { white-space: pre-wrap; line-height: 1.8; word-break: break-all; }
.muted { color: #78877e; font-size: 24rpx; line-height: 1.7; }
.row { display: flex; align-items: center; gap: 14rpx; margin-top: 18rpx; }
.row button { flex: 1; }
button { border-radius: 18rpx; font-size: 27rpx; margin: 0; padding: 6rpx 22rpx; min-height: 82rpx; }
button::after { border: 0; }
.primary { background: #24533f; color: #fff; font-weight: 600; }
.secondary { background: #edf3ed; color: #315b45; }
.ghost { background: transparent; color: #527564; border: 1rpx solid #dbe6dc; }
.small { font-size: 23rpx; }
textarea { width: 100%; min-height: 190rpx; font-size: 29rpx; line-height: 1.7; padding: 8rpx 0; }
.error { color: #9a482d; background: #fff1e7; padding: 20rpx; border-radius: 14rpx; margin-top: 20rpx; line-height: 1.7; }
.tag { display: inline-block; background: #eef3e8; color: #557348; border-radius: 9rpx; padding: 6rpx 12rpx; font-size: 22rpx; }
.empty { padding: 52rpx 20rpx; text-align: center; color: #7d8981; line-height: 1.9; background: #fbfcfa; border-radius: 20rpx; }
.hint { color: #527564; background: #f0f7f0; border-radius: 16rpx; padding: 18rpx 20rpx; line-height: 1.7; }
.danger { color: #a84c3d; }
</style>

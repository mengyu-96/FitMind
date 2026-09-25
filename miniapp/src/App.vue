<script setup lang="ts"></script>

<template><slot /></template>

<style>
page { background: #f5f6f2; color: #20372f; font-family: -apple-system, sans-serif; font-size: 28rpx; }
view, text, button, textarea { box-sizing: border-box; }
.page { padding: 36rpx 30rpx 60rpx; }
.eyebrow { color: #648578; font-size: 23rpx; letter-spacing: 4rpx; margin-bottom: 12rpx; }
.title { font-size: 50rpx; font-weight: 650; line-height: 1.3; }
.subtitle { color: #718078; line-height: 1.8; margin-top: 14rpx; }
.card { background: #fff; border-radius: 24rpx; padding: 30rpx; margin-top: 26rpx; border: 1rpx solid #e5e9e2; }
.label { font-size: 23rpx; color: #78877e; margin-bottom: 12rpx; }
.body { white-space: pre-wrap; line-height: 1.8; word-break: break-all; }
.muted { color: #78877e; font-size: 24rpx; line-height: 1.7; }
.row { display: flex; align-items: center; gap: 16rpx; margin-top: 18rpx; }
.row button { flex: 1; }
button { border-radius: 16rpx; font-size: 27rpx; margin: 0; padding: 4rpx 22rpx; }
button::after { border: 0; }
.primary { background: #244f3f; color: #fff; }
.secondary { background: #eef2e9; color: #365844; }
.small { font-size: 23rpx; }
textarea { width: 100%; min-height: 190rpx; font-size: 29rpx; line-height: 1.7; padding: 8rpx 0; }
.error { color: #9a482d; background: #fff1e7; padding: 20rpx; border-radius: 14rpx; margin-top: 20rpx; line-height: 1.7; }
.tag { display: inline-block; background: #eef3e8; color: #557348; border-radius: 9rpx; padding: 6rpx 12rpx; font-size: 22rpx; }
.empty { padding: 44rpx 0; text-align: center; color: #7d8981; line-height: 1.9; }
</style>

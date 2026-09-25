# API与事件契约

版本：v1.0｜日期：2026-09-25｜状态：C01—C10建议方案已由用户确认

## 1. 全局约定

HTTPS，前缀/api/v1，JSON字段snake_case；除登录和公共内容外使用Bearer认证。本文为评审契约，批准后实现阶段生成OpenAPI并做契约测试。所有写接口要求Idempotency-Key（登录除外），更新另带expected_version。身份从认证上下文获得，不能接收user_id改变归属。

成功包络：`{data, request_id}`；列表data为`{items,next_cursor}`，limit默认20、最大100。失败包络：`{error:{code,message,details,retryable},request_id}`。时间为ISO8601带时区，客户端业务ID和服务器UUID分开。

HTTP：400语法错误，401未认证，403权限不足，404资源不存在/非本人，409版本或幂等冲突，422字段/状态错误，429限额（带Retry-After），503暂不可用。accepted不代表业务完成。

## 2. 接口目录

| 方法与路径 | 输入要点 | 输出/权限 |
|---|---|---|
| POST /auth/wechat | code | access_token,refresh_token,expires_in,user；登录限流 |
| POST /auth/refresh | refresh_token | 轮换令牌；旧令牌失效 |
| POST /auth/logout | 当前会话 | 204，无响应体 |
| GET /me | 无 | 个人基本信息与授权状态 |
| POST /me/consents | purpose,policy_version,granted | 授权记录；撤权取消相关任务 |
| GET/PATCH /profile | PATCH: content,confirmed_fields,expected_version | 画像与version |
| POST /conversations | 无 | conversation_id |
| GET /conversations/{id}/messages | cursor,limit | 消息列表 |
| POST /conversations/{id}/messages | client_message_id,text | 202:message_id,run_id,status |
| GET /runs/{id} | 无 | 状态、最终reply、actions、citations |
| POST /runs/{id}/cancel | expected_version | 本人取消；返回已完成工具回执与取消状态，不回滚已提交事实 |
| POST /confirmations/{id}/resolve | decision=accept/reject,expected_version | 本人确认；参数哈希和资源版本匹配才执行，过期返回409 |
| GET /cards | status,location,cursor | 本人卡片 |
| POST /cards | title,type,content,display,schema_version | 201:完整卡片 |
| GET/PATCH /cards/{id} | PATCH:修改字段,expected_version | 卡片最新版本 |
| DELETE /cards/{id} | expected_version | 204；只删除卡片 |
| GET /cards/{id}/versions | cursor | 本人卡片历史 |
| POST /plans/generate | confirmed_profile_version,constraints | 202:run_id |
| GET /plans/{id} | 无 | 计划草稿或已生效版本 |
| PATCH /plans/{id} | content,expected_version | 草稿可修改；active计划修改生成新draft，原计划继续有效 |
| POST /plans/{id}/accept | expected_version | 生效计划 |
| POST /training-sessions | plan_id可空,started_at | 201:会话及version |
| PATCH /training-sessions/{id} | status,expected_version | 仅允许状态机合法迁移 |
| PUT /training-sessions/{id}/sets/{set_id} | exercise_id,ordinal,reps,weight_kg,load_mode,implement_count,rpe,completed,expected_version | 新会话版本 |
| POST /training-sessions/{id}/complete | expected_version,ended_at,feedback可空 | 会话及projection_status |
| POST /training-sessions/{id}/revisions | expected_version,reason,corrected_sets | 修订及重算状态 |
| DELETE /training-sessions/{id} | expected_version | 202:deletion_job_id；派生数据重算 |
| GET /training-sessions | from,to,exercise_id,cursor | 本人历史；单次范围≤366天 |
| GET /muscle-states | 无 | 当前估算快照，响应包含as_of；历史用趋势接口 |
| GET /muscles/{id}/history | from,to | 本人相关有效训练及可比趋势 |
| GET /exercises、/equipment | q,cursor | 已发布公共内容 |
| GET /exercises/{id}、/equipment/{id} | 无 | 完整详情与引用 |
| GET /knowledge/{id}/versions/{version} | locator可空 | 授权展示片段及来源元数据 |
| POST /feedback | target_type,target_id,category,text | 201:feedback_id |
| GET/PATCH /reminder-preferences | enabled,quiet_hours,timezone | 偏好版本 |
| GET /inbox | cursor | 站内提醒 |
| POST /inbox/{id}/read | 无 | 本人消息标记已读，重复请求幂等 |
| POST /auth/reauth | 新微信code | 当前账号匹配后签发5分钟一次性reauth_token |
| POST /me/exports | format=json | 202:job_id |
| GET /jobs/{id} | 无 | 本人任务状态；完成时短时下载链接 |
| POST /me/deletion | reauth_token,confirmation | 202:job_id；撤销全部会话 |
| POST /realtime/tickets | 无 | 单次短期连接票据 |
| POST /admin/knowledge | 元数据及草稿 | editor权限 |
| POST /admin/knowledge/{id}/review | version,decision,reason | reviewer；不能审核本人提交 |
| POST /admin/knowledge/{id}/publish | reviewed_version | reviewer/admin，必须已审核 |
| POST /admin/knowledge/{id}/withdraw | version,reason | reviewer/admin，立即查询排除 |

自定义卡片操作通过PATCH表达，P1合并拆分端点在进入该阶段时补充。公共内容可匿名读但限流，个人相关历史必须登录。

## 3. 核心结构示例

以下ID为展示用占位符，实际为UUID；示例不构成真实训练建议。

```json
{
  "card_id": "<uuid>",
  "type": "custom_energy",
  "title": "今日状态",
  "content": {"energy": "一般", "source": "user_report"},
  "display": {"location": "main", "style": "card", "priority": 60, "visible": true},
  "schema_version": 1,
  "version": 1,
  "status": "active"
}
```

```json
{
  "data": {
    "run_id": "<uuid>",
    "status": "succeeded",
    "thinking": null,
    "reply": "训练已记录，肌肉状态正在更新。",
    "actions": [{"action_id": "<uuid>", "type": "show_card", "card_id": "<uuid>", "status": "succeeded"}],
    "citations": []
  },
  "request_id": "<uuid>"
}
```

actions为已执行结果或待确认UI操作，不是客户端可任意执行的工具命令。需要确认时返回status=awaiting_confirmation和confirmation_id，确认动作必须绑定原参数哈希与版本；批准后执行同一动作，禁止模型替换参数。

run.status枚举queued/running/awaiting_confirmation/succeeded/failed/cancelled，run返回version供取消和冲突处理。awaiting_confirmation包含expires_at、操作摘要和资源版本；confirmed票据重复提交相同decision返回原结果，不同decision返回409。拒绝或过期转cancelled并说明reason。确认成功返回202及同一个run_id，恢复继续执行而非创建无关联新run。

引用结构：`{citation_id,document_id,version,chunk_id,title,locator,source_url,quoted_text}`。source_url仅允许审核域名或内部详情链接。卡片内`user_id`不由客户端提交，接口可省略，服务端存储必填。

## 4. 训练记录与单位

set必填exercise_id、ordinal、reps、load_mode、completed。load_mode枚举barbell_total/dumbbell_each/bodyweight/machine_stack；weight_kg对自重可null，其余≥0，dumbbell_each必须implement_count为1或2。器械配重不跨机型比较。RPE可null，不强迫填写。expected_version指训练会话版本，单组写入也更新会话版本。

completed会话的修改只能使用revisions，corrected_sets为完整替代快照（不是模糊增量）；服务端校验组ID无重复且属于当前会话。

## 5. 事件规范

领域事件包络：`{event_id,event_type,event_version:1,user_id,aggregate_id,aggregate_version,occurred_at,trace_id,payload}`。

| 事件 | payload | 消费方/副作用 |
|---|---|---|
| training.completed | session_id,revision | 肌肉重算、摘要、提醒取消 |
| training.revised/deleted | session_id,revision | 重算投影、失效旧摘要 |
| card.updated | card_id,version | 客户端刷新缓存 |
| muscle_state.updated | source_revision,as_of,algorithm_version | 刷新热力图 |
| plan.accepted | plan_id,version | 更新提醒安排 |
| knowledge.withdrawn | document_id,version | 缓存清除、引用标记 |
| user.consent_revoked | purpose | 停止对应处理与调度 |
| user.deletion_requested | job_id | 个人数据全链路清理 |

WebSocket路径/api/v1/realtime，使用短时票据；应用帧包含seq,type,run_id,payload。type允许run.progress/run.delta/run.awaiting_confirmation/run.cancelled/run.completed/run.failed/resource.updated。只向本人连接发送脱敏更新引用；断线后GET /runs和资源接口恢复，不能依赖WebSocket作为唯一事实来源。

## 6. 契约演进

兼容增加可选字段不升主版本；删除字段、改变语义或枚举需新版本及迁移窗口。实施时将本文转为OpenAPI/JSON Schema并锁定样例，前后端共享生成类型；在批准前不生成服务代码。

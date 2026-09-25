# API与事件契约

版本：v1.1｜日期：2026-09-25｜状态：功能业务细化同步；API尚未上线，字段变更须在首次实现前冻结

## 1. 全局约定

HTTPS，前缀/api/v1，JSON字段snake_case；除登录、刷新、注销最小回执查询和公共内容外使用Bearer认证；刷新验证refresh_token，最小回执验证receipt_token。本文为设计契约，实现阶段生成OpenAPI并做契约测试。领域写接口要求Idempotency-Key，更新另带expected_version；登录/刷新/退出/再认证/连接票据采用各自一次性凭证规则，不缓存重放令牌响应。身份从认证上下文获得，不能接收user_id改变归属。

成功包络：`{data, request_id}`；列表data为`{items,next_cursor}`，limit默认20、最大100。失败包络：`{error:{code,message,details,retryable},request_id}`。时间为ISO8601带时区，客户端业务ID和服务器UUID分开。

HTTP：400语法错误，401未认证，403权限不足，404资源不存在/非本人，409版本或幂等冲突，422字段/状态错误，429限额（带Retry-After），503暂不可用。accepted不代表业务完成。

## 2. 接口目录

| 方法与路径 | 输入要点 | 输出/权限 |
|---|---|---|
| POST /auth/wechat | code | access_token,refresh_token,expires_in,user；登录限流 |
| POST /auth/refresh | refresh_token | 轮换令牌；旧令牌失效 |
| POST /auth/logout | 当前会话 | 204，无响应体 |
| GET /me | 无 | 基本信息、用途授权、capabilities、missing_requirements |
| PATCH /me | timezone,adult_declared,expected_version | 偏好与成年声明；不能直接写角色/服务资格 |
| POST /me/consents | purpose,policy_version,granted | 授权记录；撤权取消相关任务 |
| GET/PATCH /profile | PATCH: content,confirmed_fields,expected_version | 画像与version |
| POST /conversations | 无 | conversation_id |
| GET /conversations/{id}/messages | cursor,limit | 消息列表 |
| POST /conversations/{id}/messages | client_message_id,text | 202:message_id,run_id,status |
| GET /runs/{id} | 无 | 状态、最终reply、actions、citations |
| POST /runs/{id}/cancel | expected_version | 本人取消；返回已完成工具回执与取消状态，不回滚已提交事实 |
| POST /confirmations/{id}/resolve | decision=accept/reject,expected_version | 本人确认；参数哈希和资源版本匹配才执行，过期返回409 |
| GET /cards | status,location,cursor | 本人卡片 |
| POST /cards | title,type,binding_kind,source_ref可空,content,display,pinned,schema_version | 201:完整卡片；reference内容由服务器读取，不能自填源事实 |
| GET/PATCH /cards/{id} | PATCH:修改字段,expected_version | 卡片最新版本 |
| DELETE /cards/{id} | expected_version | 204；只删除卡片 |
| GET /cards/{id}/versions | cursor | 本人卡片历史 |
| POST /plans/generate | confirmed_profile_version,constraints | 202:run_id |
| GET /plans | status,cursor | 本人计划列表；包括active和可继续的draft |
| GET /plans/{id} | 无 | 计划草稿或已生效版本 |
| PATCH /plans/{id} | content,expected_version | 草稿可修改；active计划修改生成新draft，原计划继续有效 |
| POST /plans/{id}/accept | expected_version,expected_active_plan_id（可null） | 生效计划；画像/训练/内容版本过期409 |
| POST /plans/{id}/archive | expected_version | 归档；保留已开始/历史训练和已到期履约 |
| POST /plans/{id}/revalidate | expected_version,acknowledged_changes | needs_review可复核，返回review_status；blocked不可用此接口强行解除 |
| GET /plan-occurrences | from,to,plan_id可空,cursor | 安排及履约，跨版本复用项去重 |
| POST /plan-occurrences/{id}/skip | expected_version,reason可空 | 未开始项标skipped；恢复/改期走新计划草稿 |
| POST /training-sessions | client_session_id,mode=live,plan_id可空,occurrence_id可空,timezone | 201:draft会话及version；实际开始用PATCH，单进行中约束在开始时校验 |
| GET /training-sessions/{id} | 无 | 完整会话、entries/sets、目标快照、版本及同步状态 |
| PATCH /training-sessions/{id} | status,expected_version,started_at可空,discard_confirmed可空 | 仅开始/暂停/恢复/取消；开始默认服务端当前时刻；完成必须走complete或retroactive |
| PUT /training-sessions/{id}/entries/{entry_id} | exercise_id,ordinal,status,plan_entry_id可空,expected_version | 新会话版本；同动作多条entry允许 |
| PUT /training-sessions/{id}/sets/{set_id} | entry_id,ordinal,set_kind,measurement_type,reps或duration_seconds,weight_kg,load_mode,implement_count,rpe,plan_set_id可空,completed,expected_version | 新会话版本；不直接用exercise_id作为组归属 |
| DELETE /training-sessions/{id}/sets/{set_id} | expected_version | 未结束会话删除组，返回新会话version；已结束走修订 |
| POST /training-sessions/retroactive | client_session_id,time_precision,local_date,timezone,started_at/ended_at可空,entries完整快照,occurrence_id可空 | 201:已完成会话，整次补录原子提交，单独幂等 |
| POST /training-sessions/{id}/complete | expected_version,ended_at,feedback可空 | 会话及projection_status |
| POST /training-sessions/{id}/revisions | expected_version,reason,time_precision,local_date,timezone,started_at/ended_at可空,corrected_entries | 完整替代事实快照（时间及entries含sets），修订及重算状态 |
| DELETE /training-sessions/{id} | expected_version | 202:deletion_job_id；派生数据重算 |
| GET /training-sessions | from,to,exercise_id,cursor | 本人历史；单次范围≤366天 |
| GET /muscle-states | 无 | 当前估算快照，响应包含as_of；历史用趋势接口 |
| GET /muscles/{id}/history | from,to | 本人相关有效训练及可比趋势 |
| POST /training-reports | from,to,timezone | 202:job_id，按需生成，配额与授权校验 |
| GET /training-reports/{id} | 无 | 报告、source_revision、ready/stale标记 |
| GET /exercises、/equipment | q,cursor | 已发布公共内容 |
| GET /exercises/{id}、/equipment/{id} | 无 | 完整详情与引用 |
| GET /knowledge/{id}/versions/{version} | locator可空 | 授权展示片段及来源元数据 |
| POST /feedback | target_type,target_id,category,text | 201:feedback_id |
| GET /feedback/{id} | 无 | 本人反馈状态与可读处理结果 |
| GET/PATCH /reminder-preferences | PATCH:enabled,enabled_kinds,preferred_local_time,quiet_hours,timezone,expected_version | 偏好版本；授权与平台订阅另查 |
| GET /reminders | cursor,status | 本人提醒候选，只展示非敏感业务摘要 |
| POST /reminders/{id}/snooze | expected_version,resume_at | 未投递候选延期；过期/无关409；站内信已读不等于延期 |
| GET /inbox | cursor | 站内提醒 |
| POST /inbox/{id}/read | 无 | 本人消息标记已读，重复请求幂等 |
| POST /auth/reauth | 新微信code,purpose=export/deletion | 当前账号匹配后签发绑定用途的5分钟一次性reauth_token |
| POST /me/exports | format=json,reauth_token | 202:job_id,snapshot_revision |
| GET /jobs/{id} | 无 | 本人任务状态；完成时短时下载链接 |
| POST /me/deletion | reauth_token,confirmation | 202:job_id,receipt_token；撤销全部会话与下载链接 |
| GET /deletion-receipts/{job_id} | Authorization: Receipt <receipt_token> | 仅online_blocked/physical_cleanup_status，不含个人内容；不使用URL携带token |
| POST /realtime/tickets | 无 | 单次短期连接票据 |
| POST /admin/knowledge | 元数据及草稿 | editor权限 |
| GET /admin/knowledge | status,cursor | editor/reviewer可见工作队列 |
| GET/PATCH /admin/knowledge/{id} | PATCH:expected_version,content,source,license | 草稿详情/修改；已提交修改需先撤回 |
| POST /admin/knowledge/{id}/submit | expected_version | draft→in_review |
| POST /admin/knowledge/{id}/unsubmit | expected_version | 作者撤回in_review→draft |
| POST /admin/knowledge/{id}/review | version,decision,reason | reviewer；不能审核本人提交 |
| POST /admin/knowledge/{id}/publish | reviewed_version | reviewer/admin，必须已审核 |
| POST /admin/knowledge/{id}/withdraw | version,reason | reviewer/admin，立即查询排除 |
| GET /admin/feedback | status,cursor | 经授权内容处理人员；最小化用户身份信息 |
| POST /admin/feedback/{id}/resolve | expected_version,status,resolution_code,user_visible_reply | resolved/rejected；拒绝需原因 |

自定义卡片操作通过PATCH表达，P1合并拆分端点在进入该阶段时补充。公共内容可匿名读但限流，个人相关历史必须登录。

动作/设备管理复用/admin/knowledge的CRUD、submit/unsubmit/review/publish/withdraw操作族，路径资源替换为/admin/exercises和/admin/equipment，并使用各自内容schema；发布前需同时校验引用知识与媒体权限。不把这些内部操作开放给普通用户。后台身份接入方式在上线前由主体确定，现有editor/reviewer角色仅描述权限，不代表微信普通用户可自助注册。

## 3. 核心结构示例

以下ID为展示用占位符，实际为UUID；示例不构成真实训练建议。

```json
{
  "card_id": "<uuid>",
  "type": "custom_energy",
  "title": "今日状态",
  "binding_kind": "owned",
  "source_ref": null,
  "pinned": false,
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

set必填entry_id、ordinal、set_kind、measurement_type、load_mode、completed；exercise_id归属entry，不能从传入组字段另改动作。set_kind枚举work/warmup，measurement_type=reps时reps为正整数且duration_seconds=null，duration时duration_seconds>0且reps=null。未完成组可为空；完成时必须满足计量规则。load_mode枚举barbell_total/dumbbell_each/bodyweight/machine_stack；weight_kg对自重可null，其余≥0，dumbbell_each必须implement_count为1或2。器械配重不跨机型比较。RPE可null，不强迫填写。expected_version指训练会话版本，单组写入也更新会话版本。

RPE有值时为1—10整数，与A0分段一致。PATCH取消含已完成组的会话必须带discard_confirmed=true，表明已展示放弃影响；Agent途径还需绑定确认票据，不能由模型伪造用户确认。被跳过entry不允许隐含已有完成组，冲突时要求先恢复条目或明确修改组事实。

completed会话的修改只能使用revisions，corrected_entries为动作条目及其sets的完整替代快照（不是模糊增量），同时明确时间精度与时间字段；服务端校验既有条目/组ID归属、新ID不冲突。移除所有完成组须改为整会话删除。完成响应包含completion_kind、training_revision和projection_status；已完成后换新键重试complete返回409 ALREADY_COMPLETED及原结果引用。

补录time_precision=date时local_date/timezone必填，started_at/ended_at为空，响应带derived_effective_at和估算标记；exact时完成时间范围必填且不得在未来。算法与发生日规则以23 BR-08为准。POST /training-sessions/retroactive是固定路由，应先于/{id}匹配；分页/详情不能让字符串retroactive进入UUID详情路由。

原v1.0的set.exercise_id和corrected_sets在未实施前由上述entry结构取代。本次是未上线设计的显式修订，不宣称对旧客户端兼容；首次生成OpenAPI时以v1.1为准。

## 5. 事件规范

领域事件包络：`{event_id,event_type,event_version:1,user_id,aggregate_id,aggregate_version,occurred_at,trace_id,payload}`。

| 事件 | payload | 消费方/副作用 |
|---|---|---|
| training.completed | session_id,session_version,training_revision,occurrence_id可空 | 肌肉重算、摘要、提醒取消 |
| training.revised/deleted | session_id,session_version,training_revision,occurrence_id可空 | 重算投影、失效旧摘要 |
| card.updated | card_id,version | 客户端刷新缓存 |
| muscle_state.updated | source_revision,as_of,algorithm_version | 刷新热力图 |
| plan.accepted | plan_id,version | 更新提醒安排 |
| profile.updated | profile_version,changed_field_keys | 计划复核与记忆失效；不在广播事件中携带健康值 |
| plan.archived | plan_id,version | 取消未来候选，保留历史履约 |
| plan_occurrence.changed | occurrence_id,version,status | 页面刷新与提醒候选核查 |
| knowledge.withdrawn | document_id,version | 缓存清除、引用标记 |
| content.withdrawn | entity_type,entity_id,version | 动作/设备撤回、计划资格复核 |
| user.consent_revoked | purpose | 停止对应处理与调度 |
| user.deletion_requested | job_id | 个人数据全链路清理 |

WebSocket路径/api/v1/realtime，使用短时票据；应用帧包含seq,type,run_id,payload。type允许run.progress/run.delta/run.awaiting_confirmation/run.cancelled/run.completed/run.failed/resource.updated。只向本人连接发送脱敏更新引用；断线后GET /runs和资源接口恢复，不能依赖WebSocket作为唯一事实来源。

## 6. 契约演进

兼容增加可选字段不升主版本；删除字段、改变语义或枚举需新版本及迁移窗口。实施时将本文转为OpenAPI/JSON Schema并锁定样例，前后端共享生成类型；在批准前不生成服务代码。

## 7. 业务错误与读取结构

稳定错误码与用户恢复路径见24第6节，并追加ALREADY_COMPLETED（409，引用现存完成结果）。details只返回当前用户可见对象、current_version、rule_id和allowed_actions；错误码由服务端决定，Agent不能伪造HTTP成功。

GET /muscle-states的data包含projection_status、source_revision、as_of、algorithm_version、mapping_version、coverage及muscles；同一图快照一致。projection_status为ready/updating/failed，旧快照可返回但明确stale，不把重算失败混同记录保存失败。报告任务完成后GET /jobs返回report_id，不返回导出下载链接；export/deletion/report用type区分。

DELETE路径版本置于If-Match头（数值为expected_version），避免依赖代理可能丢弃的DELETE body；目录表的expected_version遵循此约定。PATCH/POST/PUT保持JSON字段。GET游标绑定用户、过滤条件和排序字段，换过滤条件须重新分页。

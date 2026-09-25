# API与事件契约

版本：v1.4｜日期：2026-09-25｜状态：开放业务契约设计；API尚未上线，固定可信包络，业务payload允许演进

> v1.3实施范围：接口目录是跨阶段设计；M0发布子集按29 §7。未发布接口不得出现在可调用能力中，不能因为文档列出就返回伪成功。 具体分期与自主授权以[29](29-微信小程序首版收束与智能体授权.md)为准。

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
| POST /plans/generate | objective,context_refs可选,constraints可选 | 202:run_id；按本次任务取证，不要求全画像完成 |
| GET /plans | status,cursor | 本人计划列表；包括active和可继续的draft |
| GET /plans/{id} | 无 | 计划草稿或已生效版本 |
| PATCH /plans/{id} | content,expected_version | 草稿可修改；active计划修改生成新draft，原计划继续有效 |
| POST /plans/{id}/accept | expected_version,expected_active_plan_id（可null）,authorization_ref | 生效计划；仅相关依赖变化需复核，授权可来自当前明确意图或有效委托 |
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
| POST /training-sessions/{id}/revisions | expected_version,reason,semantic_patch；兼容精确编辑器的corrected_entries | 服务端构造完整源修订；两种输入互斥，返回修订及重算状态 |
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

以下仅为标准set投影：必填entry_id、ordinal、set_kind、measurement_type、completed；exercise_id归属entry，不能从传入组字段另改动作。set_kind为work/warmup，measurement_type=reps时reps为正整数且duration_seconds=null，duration时duration_seconds>0且reps=null。未完成组计量值可空；完成时满足相应计量规则。load_mode可为barbell_total/dumbbell_each/bodyweight/machine_stack或null（未知）；weight_kg任何模式均允许null，已知值须≥0。dumbbell_each的implement_count已知时为1或2，未知可null但不能用于负重比较。器械配重不跨机型比较。RPE可null。expected_version指会话投影版本，写入同时校验绑定源版本并更新同一源活动；投影条件不足仍可走开放对象保存原述。

RPE有值时为1—10整数，与A0分段一致。PATCH取消含已完成组的会话必须带discard_confirmed=true，表明已展示放弃影响；Agent途径还需绑定确认票据，不能由模型伪造用户确认。被跳过entry不允许隐含已有完成组，冲突时要求先恢复条目或明确修改组事实。

completed会话修改必须生成修订，可使用revisions语义patch或开放change-set；兼容输入corrected_entries时它是完整替代快照，与semantic_patch互斥。服务端校验既有条目/组ID归属、新ID不冲突及时间证据。移除所有有效组时保留源活动并令标准投影validity=ineligible，不能强迫删除。完成响应包含completion_kind、training_revision和消费者projection_status；已完成后换新键重试complete返回409 ALREADY_COMPLETED及原结果引用。

补录time_precision=date时local_date/timezone必填，started_at/ended_at为空，响应带derived_effective_at和估算标记；exact时完成时间范围必填且不得在未来。算法与发生日规则以23 BR-08为准。POST /training-sessions/retroactive是固定路由，应先于/{id}匹配；分页/详情不能让字符串retroactive进入UUID详情路由。

原v1.0的set.exercise_id和corrected_sets在未实施前由entry结构取代；v1.2再增加开放对象、局部语义修订及按消费者判断的资格。本次为未上线设计的显式修订，不宣称对旧客户端兼容；首次生成OpenAPI以v1.2为准。

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

固定包络与系统控制字段用严格Schema；业务payload不是全局固定字段白名单。个人schema可选且按用户/版本解释，新增kind无需修改全局枚举。本文v1.2修订的是尚未上线的设计基线，不代表可以对已发布接口静默破坏兼容。

## 7. 业务错误与读取结构

稳定错误码与用户恢复路径见24第6节，并追加ALREADY_COMPLETED（409，引用现存完成结果）。details只返回当前用户可见对象、current_version、rule_id和allowed_actions；错误码由服务端决定，Agent不能伪造HTTP成功。

GET /muscle-states的data包含projection_status、source_revision、as_of、algorithm_version、mapping_version、coverage及muscles；同一图快照一致。projection_status为ready/updating/failed，旧快照可返回但明确stale，不把重算失败混同记录保存失败。报告任务完成后GET /jobs返回report_id，不返回导出下载链接；export/deletion/report用type区分。

DELETE路径版本置于If-Match头（数值为expected_version），避免依赖代理可能丢弃的DELETE body；目录表的expected_version遵循此约定。PATCH/POST/PUT保持JSON字段。GET游标绑定用户、过滤条件和排序字段，换过滤条件须重新分页。

## 8. 柔性对象与可组合能力接口（v1.2）

| 方法与路径 | 输入与语义 | 响应/限制 |
|---|---|---|
| GET /capabilities | 当前任务上下文引用可选 | 可用工具、最小输入、效果类别、权限与消费者条件；服务端执行时重新核查 |
| POST /objects | kind,payload,source_refs可选,schema_ref可选 | 201：正式保存的对象与消费者资格；不因无组数/重量返回422 |
| GET /objects、/objects/{id} | 本人范围、kind/关系/时间过滤、游标 | 源对象及版本，未知时间单独分组，不虚构排序日期 |
| PATCH /objects/{id} | expected_version,semantic_patch,operation_id | 通过统一变更服务更新；系统属性不可在payload中覆盖 |
| POST /change-sets | intent_ref,operations,base_versions,operation_id | 变更提案及真实效果摘要；模型不能自授权限 |
| POST /change-sets/{id}/validate | expected_version | 校验回执、影响、待补证据及可行部分；未写业务事实 |
| POST /change-sets/{id}/commit | expected_version,validation_ref,authorization_ref | 提交结果；授权不足才返回需要确认，验证失效409 |
| GET /operations/{id} | 稳定operation_id | 已提交/待执行/失败及实际成功对象引用，跨run可恢复 |
| POST /objects/{id}/projections | consumer,expected_version | 200即时或202异步；不新建第二场活动 |
| GET/POST /personal-schemas | 本人类型及可选属性定义 | 版本化个人语义；不含权限字段，默认不强制全量必填 |
| POST /views/compose | object_refs,display_intent或注册组件树 | 受控渲染视图；未知组件降级保留源内容 |
| GET/POST /mandates | POST：用户明确指令来源、scope/actions/effect_limits/expiry | 用户可见委托；服务端验证授权证据，模型自述“用户同意”无效 |
| POST /mandates/{id}/revoke | expected_version | 立即阻止后续提交；不回滚已执行操作 |
| GET/POST /inquiries | POST：topic,purpose,evidence_refs,decision_impact | 本人议题及状态；可主动创建，不能自动标记用户已答 |
| POST /inquiries/{id}/responses | text或message_ref,expected_version,disposition可选 | 自然回复/不知道/拒答/延期；返回相关事实与议题更新 |
| POST /coaching-feedback | observation_refs,interpretation,proposed_next_step可选 | 区分观察与假设；发送当前会话反馈，离线投递另走授权调度 |
| GET/PATCH /interaction-preferences | 主动程度、免问主题、期限、expected_version | 与reminder-preferences独立；自然语言设置走同一服务 |

所有新私有写接口适用鉴权、用途、Idempotency-Key和版本规则。source_refs、intent_ref、authorization_ref必须可验证，不能通过传入他人ID或伪造证据绕过授权。更新对象与change-set两种入口共享同一提交器。精确训练/画像接口是同一源对象的适配器，并非Agent必须填写的表单。

semantic_patch的操作信封固定为目标object_ref、op（replace/remove/append/link）、path、value或related_ref、evidence_refs；业务path允许个人新属性。每种op按能力声明解释，数组修改用稳定子项ID而非脆弱位置索引。服务端拒绝修改owner/授权/系统版本、跨用户引用、原型污染键及超资源预算请求。首次创建可由服务端将Idempotency-Key绑定生成operation_id并返回；Agent网关提前生成稳定operation_id，重试必须复用，不能在新run重新建同一对象。

卡片示例中的source_ref=null只表示owned创建请求尚未分配源对象；成功响应必须返回服务端建立的源对象引用。普通用户可编辑新业务属性，系统身份与授权字段仍只通过专用服务维护。

开放记录成功示意（服务端生成ID/版本/资格；请求只需真实内容）：

```json
{
  "data": {
    "object_id": "activity-example",
    "version": 1,
    "saved": true,
    "kind": "activity_report",
    "payload": {"description": "今天练腿，很累", "activity_status": "finished"},
    "eligibility": {
      "history": "eligible",
      "a0": {"status": "ineligible", "reasons": ["NO_MAPPED_WORK_SETS"]},
      "e1rm": {"status": "ineligible", "reasons": ["NO_COMPARABLE_LOAD"]}
    },
    "suggested_followup": null
  },
  "request_id": "request-example"
}
```

保存成功不以用户回答后续问题为条件。`ACTION_EVIDENCE_INSUFFICIENT`仅阻止当前缺证据的执行动作，返回action、needed_evidence、allowed_actions；不使用PROFILE_INCOMPLETE作为全局门槛。建议性信息缺口放在成功响应中。标准complete的NO_COMPLETED_SETS不适用于开放源记录。

## 9. 开放事件与主动交互恢复

新增`object.created/revised/deleted`（object_id、version、kind）、`activity.changed`（activity_id、training_revision、activity_status）、`projection.updated`（object_id、consumer、source_version、projection_version）、`inquiry.updated/resolved`（inquiry_id、version、answer_revision）、`mandate.revoked`（mandate_id、version）。事件只携带引用与必要路由信息，不广播健康正文。

training.completed/revised/deleted保留为标准适配器事件，与activity.changed共用operation_id和source_activity_id；统计按源活动ID去重并按metric_definition_version判断资格，不能把两种事件相加。补齐字段、重建投影和重复消费不会增加训练场次。消费者按源版本CAS，过期答案或旧议题任务不可覆盖新理解。

当前对话内主动问题和反馈随assistant消息持久化；返回时的候选开场是独立预览，未展开/回答不自动写入聊天或inbox。跨设备回答后同步inquiry版本、撤下过时提示。离线投递当前不实现，未来若实验再核验通道与授权。呈现竞态、拒答与延期以28为准。

## 10. M0接口与工具发布策略

M0优先实现auth/me/consents、conversation/message/run、objects、operations、基本plans、cards、知识/动作引用读取、interaction_preferences、inquiries、mandates、feedback及导出/删除。plan-occurrences完整履约、training-sessions实时开始暂停计时、muscle-state、training-reports任务、reminders/inbox、个人Schema管理和运营Web接口后置；记录主入口为objects。内容发布/撤回仍通过受限内部接口或导入工具完成。

新增`POST /agent-actions/apply`作为apply_changes能力的HTTP适配，输入operation_id、operations、expected_versions、intent_ref/mandate_ref；归属由服务端注入。响应包含executed/pending_confirmation/rejected及每项回执，已授权时一次请求内完成内部验证与提交；需要确认时复用confirmations。校验不通过的原子组不部分落库，用户允许的独立组可明确部分成功。不要求用户或模型先调用三次接口才保存一句话。

`GET /capabilities`附release=M0及实现/授权状态；能力描述可以被模型动态发现，自由组合，实际提交仍重新校验。未来接口未实现返回明确NOT_IMPLEMENTED_IN_RELEASE（501）或不注册路由；权限缺失与能力不存在区分，Agent不能把后者解释成“再给权限即可执行”。所有开放写入包括直接对象入口复用同一效果校验与授权服务。

首版不存在后台提醒投递，manage_inquiry只保存并在下一次前台交互读取。持续委托授予/撤销可通过现有mandates或统一变更入口完成，不因为没有独立管理页面就限制Agent在已授范围内行动。

M0 plans使用稳定node_id与源活动显式关系表示已执行部分，保持一个active主计划及历史版本；不依赖plan-occurrences接口才能保存或调整计划。apply_changes可直接激活/调整经授权计划，仍在事务内核对expected_active_plan_id和相关源版本。撤销通过引用原operation_id创建逆向语义修订，同样验证当前版本与后续依赖，不能无声覆盖后来修改。

## 11. 前台续接最小契约（v1.4）

`POST /conversations/{id}/resume`接收稳定client_resume_id、当前page及客户端交互代次；服务端识别visit、读取本人议程/偏好并去重。有现成决定返回200及decision=none/offer；需生成返回202及run_id，经GET /runs恢复；客户端页面不等待该结果才能使用。offer包含engagement_id、inquiry_ref/version、answer_revision、presentation_token及expires_at。当前无AI用途、免开场或无有用议题返回none，不创建新的主动模型任务，也不误报全部功能不可用。

`POST /engagements/{id}/ack`接收presentation_token及action=shown/dismissed/opened；当前用户、展示占位、版本和交互代次由服务端复核，重复动作幂等；过期返回STALE_ENGAGEMENT（409）并由客户端安静丢弃。opened才将对应候选衔接为正常对话；回答仍走已有消息入口，可携engagement_ref关联，一段自然回答可以解决多个议题。

client_resume_id按用户唯一，客户端不凭自填page/visit扩大业务权限。新消息或偏好更改递增交互代次，旧候选不能发布为当前问题；页面隐藏本地立即停止呈现。端间网络延迟无法保证瞬时撤回已显示内容，收到版本失效时撤下/标已更新，不再次推送解释。候选呈现不触发业务计划写入；授权内自主调整仍走独立apply_changes回执。

旧reminder-preferences/reminders/inbox路由为非M0、非默认V1的历史候选协议，当前能力发现不得返回可执行。schedule_followup若保留工具别名，回执明确mode=next_interaction、notification_scheduled=false，不使用含糊“已设置提醒”。

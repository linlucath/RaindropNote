# 任务进度页设计

## 背景

当前产品有两条和任务相关的能力：

- `生成历史`：适合查看已经落地的结果
- 首页轮询：适合感知“当前任务还在跑”

但它们都不适合作为任务管理界面。用户现在缺少三种关键能力：

1. 集中查看所有正在运行的任务
2. 明确知道任务走到了哪个阶段
3. 主动结束单任务或停止批量任务

本设计新增一个独立的 `任务进度` 页面，作为“任务控制台 + 轻量流水线监控”的组合页。

## 目标

- 让用户一眼看到当前系统正在处理什么
- 让单任务和批量任务都具备统一的进度感知
- 提供可理解、可恢复的停止任务能力
- 不打断现有首页和生成历史的使用习惯

## 非目标

- 不做 WebSocket 或服务端推送，第一版继续使用轮询
- 不做线程级强杀；停止能力采用“软停止”
- 不做复杂筛选、排序、标签管理
- 不做下载/转写的百分比级进度条，只展示阶段进度

## 用户体验

### 信息架构

新增独立页面：`任务进度`

页面包含两层：

1. 顶部总览
   - `排队中`
   - `进行中`
  - `已完成`
  - `已失败`
  - `已取消`
  - `正在停止`
2. 下方任务列表
  - 默认展示 `活跃任务 + 最近终态任务`
  - 提供轻量过滤：`只看活跃任务`
   - 批量任务与单任务统一显示为卡片

### 单任务卡片

每张卡片显示：

- 视频标题
- 平台
- 当前阶段
- 当前状态文案
- 创建时间
- 最近更新时间
- 操作按钮：`查看结果`、`结束任务`、`重试`（失败时）

阶段文案使用后端枚举映射：

- `PENDING` -> 排队中
- `PARSING` -> 解析链接
- `DOWNLOADING` -> 下载中
- `TRANSCRIBING` -> 转写中
- `SUMMARIZING` -> 总结中
- `FORMATTING` -> 格式化中
- `SAVING` -> 保存中
- `SUCCESS` -> 已完成
- `FAILED` -> 失败
- `CANCELLING` -> 正在停止
- `CANCELLED` -> 已取消

### 批量任务卡片

默认折叠展示：

- 批次标题（优先用来源链接摘要或“批量文字稿任务”）
- 当前批次状态
- 总进度：`completed / total`
- 当前正在处理的子任务标题
- 最近更新时间
- 操作按钮：`展开详情`、`停止批量`

展开后显示子任务列表，每条仅保留：

- 视频标题
- 状态
- 结果入口
- 错误信息（如果失败）

### 停止任务交互

第一版统一采用软停止：

- 单任务：点击 `结束任务` 后，状态变为 `CANCELLING`
- 若任务还未真正开始执行，则直接进入 `CANCELLED`
- 若任务已在执行中，则在下一个安全检查点退出，最终进入 `CANCELLED`

批量任务：

- 点击 `停止批量` 后，批次状态先切换为 `CANCELLING`
- 批次标记为 `cancel_requested = true`
- 当前正在执行的子任务同步收到取消意图
- 正在执行中的当前子任务继续执行到安全检查点
- 后续未开始的子任务统一标记为 `CANCELLED`
- 批次整体最终进入 `CANCELLED`

UI 原则：

- 停止动作需要二次确认
- 停止后卡片文案立即切换为“正在停止”
- 停止成功后按钮替换为“已取消”

## 任务集合来源

为了让进度页在刷新后仍然成立，第一版不依赖“前端记住 task_id/batch_id 再逐条轮询”的方式拼页面，而是引入统一聚合接口。

新增接口建议：

- `GET /progress/overview`

返回内容包含：

1. 活跃单任务列表
2. 活跃批量任务列表
3. 最近终态单任务列表
4. 最近终态批量任务列表
5. 顶部统计块所需聚合计数

这保证：

- 页面刷新后仍能恢复任务视图
- 顶部统计和卡片列表来自同一份后端视图
- 前端仍可对活跃任务做增量轮询，但不再承担“发现任务集合”的职责

### 任务进度页范围

第一版页面默认展示：

- 全部活跃任务
- 最近终态任务（建议最近 20 条）

而不是无限制展示所有历史任务。历史长尾继续由 `生成历史` 承担。

## 技术方案

## 前端

### 路由与入口

- 新增 `任务进度` 路由页
- 在现有导航中增加入口
- 首页和历史页不下线，职责保持：
  - 首页：提交任务与查看当前结果
  - 历史页：浏览已生成内容
  - 任务进度页：管理与监控任务

### 状态管理

优先扩展现有 `taskStore`，不新建第二套并行 store。

新增两类数据：

1. `activeTasks`
   - 单任务的实时状态快照
2. `activeBatches`
   - 批量任务的实时状态快照

建议数据结构：

```ts
type RuntimeTaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLING'
  | 'CANCELLED'

type BatchStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'CANCELLING'
  | 'CANCELLED'
  | 'SUCCESS'
  | 'FAILED'

type BatchItemStatus =
  | RuntimeTaskStatus
  | 'SKIPPED'

interface ProgressTaskItem {
  id: string
  title: string
  platform: string
  status: RuntimeTaskStatus
  message?: string
  createdAt?: string
  updatedAt?: string
  isBatchChild?: boolean
}

interface ProgressBatchItem {
  batchId: string
  title: string
  sourceLabel?: string
  status: BatchStatus
  completed: number
  total: number
  updatedAt?: string
  currentItemTitle?: string
  currentItemIndex?: number
  cancelRequested?: boolean
  items: Array<{
    video_id: string
    title: string
    status: BatchItemStatus
    task_id?: string | null
    message?: string
  }>
}
```

过滤规则：

- `只看活跃任务` 包含：
  - 单任务：`PENDING/PARSING/DOWNLOADING/TRANSCRIBING/SUMMARIZING/FORMATTING/SAVING/CANCELLING`
  - 批次：`PENDING/RUNNING/CANCELLING`
- `SKIPPED` 归类为已完成语义，用于批量子任务显示，不进入单独统计块

### 轮询

沿用当前轮询模型，但拆成两类：

- 聚合轮询：基于新增 `progress/overview`
- 单任务详情轮询：基于已有 `task_status/{task_id}`
- 批量详情轮询：基于已有 `batch/status/{batch_id}`

策略：

- 活跃任务每 3 秒轮询
- 无活跃任务时自动暂停
- 页面离开后停止订阅

说明：

- 进度页主列表优先使用聚合接口
- 单条任务或展开批量详情时，才按需请求详情接口
- 这样可以避免前端同时维护大量未知 id 的轮询集合

### 页面组件拆分

建议新增：

- `TaskProgressPage.tsx`
- `TaskOverviewBar.tsx`
- `TaskProgressCard.tsx`
- `BatchProgressCard.tsx`
- `BatchProgressDetails.tsx`

保持卡片职责单一，避免把所有逻辑继续堆回首页。

## 后端

### 单任务取消

新增接口：

- `POST /cancel_task`

请求：

```json
{
  "task_id": "uuid"
}
```

行为：

- 若任务尚未完成，则写入取消意图
- 状态文件更新为 `CANCELLING`
- `NoteGenerator` 在关键阶段之间检查取消标记
- 命中后写入 `CANCELLED`

### 批量任务取消

新增接口：

- `POST /batch/cancel`

请求：

```json
{
  "batch_id": "uuid"
}
```

行为：

- 将批次标记为 `cancel_requested = true`
- 批次状态立即更新为 `CANCELLING`
- 如果当前批次有正在运行的子任务，向对应 `task_id` 同步写入取消意图
- `run_batch` 在每个子任务开始前检查批次标记
- 命中后：
  - 当前未启动项目标记为 `CANCELLED`
  - 当前运行项目在任务级安全检查点退出
  - 批次整体标记为 `CANCELLED`

### 状态模型扩展

扩展 `TaskStatus`：

- `CANCELLING`
- `CANCELLED`

批次状态单独建模，不复用单任务枚举：

- `PENDING`
- `RUNNING`
- `CANCELLING`
- `CANCELLED`
- `SUCCESS`
- `FAILED`

批量子任务保留现有 `SKIPPED`，并定义其产品语义为“已完成且复用已有结果”。

并在状态文件中补充：

- `updated_at`
- `message`
- `title`
- `platform`
- `created_at`

批量状态中补充：

- `updated_at`
- `cancel_requested`
- `current_item_title`
- `current_item_index`
- `title`
- `source_label`
- `created_at`

### 聚合视图 DTO

新增进度页聚合接口的返回结构：

```json
{
  "summary": {
    "pending": 1,
    "running": 3,
    "cancelling": 1,
    "success": 12,
    "failed": 2,
    "cancelled": 1
  },
  "tasks": {
    "active": [],
    "recent_terminal": []
  },
  "batches": {
    "active": [],
    "recent_terminal": []
  }
}
```

这样前端不需要拼接首页 store、历史接口和批量接口来构造进度页。

### 安全检查点

为了避免强杀线程，取消检查放在这些阶段之间：

- 解析完成后
- 下载完成后
- 转写完成后
- 总结完成后
- 保存前

批量任务的当前子任务如果已绑定 `task_id`，则批量取消会联动设置该任务的取消意图，从而让当前子任务也能在这些检查点退出。

这意味着第一版“结束任务”是软停止，但行为稳定、易于解释。

## 兼容性

- 现有 `生成历史` 数据结构继续可用
- 现有首页表单提交流程不需要重写
- 批量任务现有接口只做补充，不破坏已有字段
- 首页和现有轮询逻辑需要同步纳入 `CANCELLING/CANCELLED` 终态识别，避免把已取消任务继续当成进行中

## 错误处理

- 取消失败：提示“结束任务失败，请稍后重试”
- 查询失败：进度页展示轻量错误提示，不阻塞已渲染内容
- 任务已经完成时取消：返回幂等成功，前端仅刷新状态

## 测试策略

### 后端

- 单任务取消接口：
  - 正在排队时取消
  - 正在执行时取消
  - 已完成任务取消的幂等性
- 批量取消接口：
  - 未开始批次取消
  - 执行中批次取消
  - 已取消批次重复取消

### 前端

- 进度页聚合接口渲染正确
- 进度页统计卡计算正确
- 活跃任务过滤正确
- 单任务卡片状态映射正确
- 批量任务展开/折叠正确
- `SKIPPED` 的完成语义展示正确
- 点击结束任务后状态从 `CANCELLING` 到 `CANCELLED`
- 首页与任务进度页对 `CANCELLED` 的终态识别一致

## 实现顺序

1. 扩展后端状态枚举与状态文件字段
2. 增加单任务取消接口与软停止检查
3. 增加批量取消接口与批次停止逻辑
4. 扩展前端 service 与 store
5. 新增 `任务进度` 页面与卡片组件
6. 接入轮询与交互按钮
7. 完成回归测试与本地联调

## 取舍说明

本设计故意没有引入 WebSocket、实时百分比进度、线程强杀。

原因是当前项目的任务执行模型基于状态文件与串行执行器，这种结构更适合先把“阶段可见、状态可停、批量可控”做稳。等这版稳定后，再考虑是否要把任务系统升级成更实时的推送模型。

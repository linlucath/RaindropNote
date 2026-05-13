# Bilibili 关注 UP 主选择与批量转换设计

## 背景

当前项目已经支持两种和 Bilibili 批量处理相关的能力：

- 用户在首页选择 `UP 主批量`，手动输入 `space.bilibili.com` 主页链接
- 后端通过 `yt-dlp` 拉取该 UP 主视频列表，前端勾选视频后复用现有批量任务链路

这次要补充的能力不是再次输入某个 UP 主主页，而是基于用户已经配置的 Bilibili Cookie，直接读取“当前账号已关注的 UP 主列表”，然后从中选择某个 UP 主，再查看该 UP 主的全部视频并按需转换。

## 目标

- 在现有首页 `UP 主批量` 模式中新增“从关注列表选择”的来源
- 后端基于 Bilibili Cookie 获取当前账号已关注的 UP 主列表
- 前端支持分页浏览、昵称搜索、选择单个 UP 主
- 选中某个 UP 主后，展示该 UP 主的视频列表
- 用户可勾选全部或部分视频，继续复用现有批量转换流程

## 非目标

- 不支持一次同时选择多个 UP 主混合批量
- 不改造现有批量任务执行、轮询、结果查看主流程
- 不在第一版支持关注分组、特别关注、排序高级筛选等复杂能力
- 不依赖浏览器页面抓取 `relation/follow` HTML 作为正式数据源

## 用户流程

### 1. 首页入口

用户在首页选择：

- `任务`: `UP 主批量`
- `视频来源`: `手动输入主页` 或 `从关注列表选择`

默认保留现有“手动输入主页”能力，新能力作为并列来源出现。

### 2. 从关注列表选择

当用户选择 `从关注列表选择` 时：

1. 前端检查 Bilibili Cookie 是否存在
2. 若不存在，展示引导文案，提示去设置页填写
3. 若存在，允许用户点击“拉取关注列表”
4. 前端请求后端关注列表接口，获得分页数据
5. 页面展示 UP 主列表，支持关键词搜索和加载更多
6. 用户点击某个 UP 主
7. 前端请求该 UP 主视频列表接口
8. 页面展示视频列表，沿用现有批量预览与勾选交互
9. 用户提交后，进入现有批量任务处理流程

### 3. 手动输入主页

保持现有交互不变：

- 输入 `https://space.bilibili.com/{mid}`
- 拉取该 UP 主视频列表
- 勾选视频后提交

## 交互设计

## 页面结构

在现有 `NoteForm` 的 `UP 主批量` 模式下新增一个二级来源切换：

- `手动输入主页`
- `从关注列表选择`

### 当来源为“手动输入主页”

保持现有字段：

- UP 主主页输入框
- 最多视频数
- 跳过已处理
- 拉取按钮
- 视频预览区

### 当来源为“从关注列表选择”

展示以下区域：

- 关注列表操作栏
  - `拉取关注列表` 按钮
  - 搜索框，按 UP 主昵称过滤
- 关注 UP 主列表
  - 头像
  - 昵称
  - 简介或签名
  - 选中态
  - 加载更多
- 已选 UP 主的视频列表
  - 与现有 `BatchVideoPreview` 结构尽量一致

## 关键交互规则

- 第一次进入“从关注列表选择”时，不自动请求，避免页面初始化触发慢请求
- 切换搜索关键词时，重置分页并重新拉取关注列表
- 选中新的 UP 主时，清空上一个 UP 主的视频预览与选中状态
- 修改“最多视频数”后，如果视频列表已经拉取过，标记为过期，要求重新拉取
- 批量提交时，只提交当前选中的视频 URL 列表，不提交 UP 主信息作为执行主数据

## 后端设计

## 方案选择

采用“Bilibili 接口 + Cookie 请求”的方案，而不是抓取 `relation/follow` 页面 HTML。

原因：

- 分页与搜索更稳定
- 结构化数据更适合前后端协作
- 对页面结构变化更不敏感
- 更容易返回明确错误，例如登录失效、权限不足、风控拦截

## 新增服务能力

建议新增一个专门的 Bilibili 关注数据服务模块，例如：

- `backend/app/services/bilibili_follow_service.py`

该服务负责：

- 读取 Bilibili Cookie
- 组装请求头与 Cookie
- 请求关注列表接口
- 标准化返回数据
- 处理分页、搜索、错误映射

## 新增接口

### 1. 关注 UP 主列表

建议接口：

`GET /bilibili/followings`

请求参数：

- `page`: 页码，默认 1
- `page_size`: 每页数量，默认 20
- `keyword`: 可选，按昵称搜索

返回结构建议：

```json
{
  "items": [
    {
      "mid": "558268687",
      "name": "UP主昵称",
      "face": "https://...",
      "sign": "个性签名"
    }
  ],
  "page": 1,
  "page_size": 20,
  "has_more": true,
  "total": 120
}
```

行为说明：

- 后端从配置中读取 `bilibili` cookie
- 若缺少 cookie，返回业务错误，提示先配置
- 若 cookie 失效或接口拒绝访问，返回明确错误信息
- 如果接口本身支持昵称搜索，则后端透传；否则后端先分页拉取后做本页过滤，第一版优先简单实现

### 2. 指定 UP 主视频列表

建议接口：

`GET /bilibili/uploader_videos`

请求参数：

- `mid`: 必填，UP 主 mid
- `limit`: 可选，最多返回视频数，默认 20，`0` 表示不限制，上限 500

返回结构尽量对齐现有批量视频预览：

```json
[
  {
    "video_id": "BVxxxx",
    "video_url": "https://www.bilibili.com/video/BVxxxx",
    "title": "视频标题"
  }
]
```

实现优先级：

- 第一版优先复用现有 `preview_bilibili_space` 逻辑
- 后端根据 `mid` 组装 `https://space.bilibili.com/{mid}/upload/video`
- 复用已有 `normalize_bilibili_entries` 和标题补全逻辑

这样可最大限度减少新逻辑，只是把入口从“用户手填 URL”扩展为“由 mid 生成 URL”。

### 3. Cookie 可用性检查

建议补一个轻量接口，避免前端只能在请求失败后才知道没配置 cookie：

`GET /bilibili/cookie_status`

返回结构建议：

```json
{
  "configured": true
}
```

第一版也可以不单独建接口，直接复用现有 `/get_downloader_cookie/bilibili` 判断是否为空。如果倾向最小改动，可以先复用现有接口。

## 前端设计

## 状态扩展

在 `NoteForm` 中新增表单与页面状态：

- `uploader_source_mode`: `manual` | `followings`
- `selected_uploader_mid`
- `selected_uploader_name`
- `following_keyword`
- `followings_page`
- `followings_loading`
- `followings_has_more`
- `followings`

批量视频相关状态尽量复用现有：

- `previewVideos`
- `selectedBatchVideoIds`
- `previewSignature`
- `batchStatus`

## 组件拆分建议

为了避免 `NoteForm.tsx` 继续膨胀，建议新增一个专门组件，例如：

- `BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx`

它负责：

- 拉取关注 UP 主列表
- 搜索与分页
- 展示当前选中的 UP 主
- 触发“拉取该 UP 主视频”

`NoteForm` 负责：

- 来源模式切换
- 表单提交
- 与现有批量视频预览拼接

## 提交逻辑

批量提交逻辑保持不变：

- 前端仍然把选中的视频标准化成 `videos: BatchVideo[]`
- 调用现有 `startBatch`
- 后端现有 `run_batch` 无需知道来源是“手动主页”还是“关注列表选择”

这样能保证最小回归风险。

## 数据流

### 关注列表

```text
用户点击拉取关注列表
-> 前端请求 /bilibili/followings?page=1&page_size=20&keyword=xxx
-> 后端带 cookie 请求 B 站关注接口
-> 返回标准化关注列表
-> 前端展示并维护分页状态
```

### 某个 UP 主的视频列表

```text
用户点击某个 UP 主
-> 前端记录 selected_uploader_mid
-> 前端请求 /bilibili/uploader_videos?mid=xxx&limit=xxx
-> 后端组装 space URL 并复用现有批量预览逻辑
-> 返回视频列表
-> 前端展示勾选区
```

### 批量任务提交

```text
用户勾选视频并提交
-> 前端调用现有 /batch/start
-> 后端沿用现有 run_batch
-> 任务状态展示与结果查看完全复用现有链路
```

## 错误处理

需要覆盖以下场景：

- 未配置 Bilibili Cookie
  - 前端提示“请先到设置页填写 Bilibili Cookie”
- Cookie 已失效
  - 后端返回“Cookie 已失效，请重新登录并更新”
- 关注列表为空
  - 前端展示空状态，不视为报错
- 关注列表拉取失败
  - 前端 toast + 列表区错误提示
- 某个 UP 主没有公开视频
  - 视频列表空状态
- 该 UP 主视频列表拉取失败
  - 保留已选 UP 主，但清空视频区并提示重试

## 测试设计

## 后端测试

新增或扩展测试覆盖：

- `followings` 接口在无 cookie 时返回业务错误
- `followings` 接口在请求成功时返回标准化分页结构
- `followings` 接口在 B 站返回未登录时正确映射错误
- `uploader_videos` 接口根据 mid 正确组装空间地址
- `uploader_videos` 接口复用现有视频标准化逻辑

建议新增测试文件：

- `backend/tests/test_bilibili_follow_router.py`
- 或按当前风格合并进已有 `batch` / `config` 相关测试

## 前端测试

至少覆盖这些行为：

- 切换 `UP 主批量` 来源模式时，界面字段正确切换
- 关注列表模式下，未配置 cookie 时展示提示
- 拉取关注列表成功后，能展示并选择 UP 主
- 切换 UP 主后，视频预览区更新
- 视频勾选后，提交 payload 与现有 `startBatch` 结构一致

如果当前项目没有完善的前端测试基础，第一版至少补充手工验证清单并通过构建/lint 验证。

## 实施顺序

1. 后端补充 Bilibili 关注列表服务
2. 新增关注列表与指定 UP 主视频列表接口
3. 前端补充 `UP 主批量` 来源模式切换
4. 前端实现关注列表组件与分页搜索
5. 复用现有视频预览与批量提交
6. 补测试与手工回归

## 风险

- Bilibili 接口对 cookie 字段依赖可能比预期更严格，可能需要补充 `User-Agent`、`Referer`、`Origin`
- 若直接使用网页登录 cookie，请求可能触发风控，需要在错误提示中给出可操作反馈
- `NoteForm.tsx` 当前已较大，如果继续直接堆逻辑，维护成本会明显上升，因此建议顺手拆出关注列表选择组件

## 推荐结论

推荐在现有 `UP 主批量` 模式内新增“从关注列表选择”来源，并采用“后端基于 Bilibili Cookie 请求关注接口 + 前端分页选择 + 复用现有批量视频预览与提交”的方案。

这是当前代码结构下改动最集中、回归风险最低、后续也最容易继续增强的实现路径。

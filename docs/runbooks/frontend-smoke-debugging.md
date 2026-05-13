# Frontend Smoke Debugging Runbook

本 runbook 用来处理 BiliNote 前端里“代码层测试通过，但真实页面交互仍然报错”的问题。

适用场景：
- 批量选择、表单切换、按钮点击、弹窗开关这类交互问题
- React 组件在真实重渲染时才暴露的问题
- 需要在不依赖 MCP 的前提下完成本地复现、修复、验证

## 核心原则

1. 不要只停留在纯函数或源码级测试。
2. 必须补一条能跑真实页面交互的本地冒烟测试。
3. 先抓到浏览器里的真实异常，再决定修哪里。
4. 修复后同时保留冒烟测试和轻量回归测试，避免回归。

## 本地调试入口

前端目录：`BillNote_frontend`

关键命令：

```bash
cd BillNote_frontend
pnpm install
pnpm exec playwright install chromium
pnpm smoke:batch-selection
```

如果只想跑当前批量选择的用例：

```bash
cd BillNote_frontend
pnpm smoke:batch-selection
```

如果要跑本次相关的轻量回归测试：

```bash
cd BillNote_frontend
node --test \
  src/pages/HomePage/components/batchVideoSelection.test.ts \
  src/components/ui/ref-forwarding.test.js \
  src/components/ui/switch.test.js
```

## 推荐流程

### 1. 先缩小问题范围

先用 `rg` 找到真实交互入口、状态持有者、纯逻辑辅助函数。

本次“批量选择清空报错”的实际链路是：

- 交互入口：`BillNote_frontend/src/pages/HomePage/components/BatchVideoPreview.tsx`
- 状态持有：`BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- 选择辅助逻辑：`BillNote_frontend/src/pages/HomePage/components/batchVideoSelection.ts`

### 2. 先补真实页面冒烟测试

不要先猜根因，先把用户操作路径自动化。

本仓库的 Playwright 配置和当前案例用例：

- `BillNote_frontend/playwright.config.ts`
- `BillNote_frontend/tests/smoke/batch-selection.spec.ts`

当前用例覆盖的路径：

1. 打开首页
2. 切到 `UP 主批量`
3. 填入主页链接
4. 拉取视频列表
5. 选择两条视频
6. 点击 `全不选`
7. 断言计数从 `2 / 3` 回到 `0 / 3`
8. 断言没有 `pageerror`
9. 断言没有 `console error`

### 3. 用接口桩隔离前端

前端交互问题先不要依赖真实后端。

在 Playwright 里用 `page.route('**/api/**', ...)` mock 掉：

- `/api/sys_check`
- `/api/sys_health`
- `/api/model_list`
- `/api/batch/preview`
- 其他当前页面启动必需接口

这样可以把问题限制在：
- 组件渲染
- 状态流转
- DOM 事件
- React 兼容性

而不是被后端波动干扰。

### 4. 一定要抓浏览器运行时异常

冒烟测试里要主动记录：

```ts
page.on('pageerror', error => {
  pageErrors.push(error.message)
})

page.on('console', message => {
  if (message.type() === 'error') {
    consoleErrors.push(message.text())
  }
})
```

很多问题表面上是“第二次点击无效”，真实根因其实是“第一次点击后页面已经崩了”。

### 5. 如果结果异常，先验证页面是不是已经崩掉

遇到这类现象：

- 第二次点击找不到元素
- 元素突然消失
- 整个 `body` 内容变空
- 计数文本不再更新

优先怀疑：

- `Maximum update depth exceeded`
- ref 循环更新
- 受控/非受控组件冲突
- 第三方 UI primitive 与 React 版本不兼容

## 本次问题的定位结论

本次不是“批量选择清空逻辑”本身写错了。

真实根因是：

- 点击视频后触发了页面局部重渲染
- 页面中的 `Switch` / `Checkbox` 使用了 Radix primitive
- 在 React 19 下触发 ref 更新环
- 浏览器抛出 `Maximum update depth exceeded`
- 页面崩掉后，第二条视频和“全不选”自然都失效

实际抓到的关键错误：

```text
Maximum update depth exceeded. This can happen when a component repeatedly calls setState inside componentWillUpdate or componentDidUpdate.
```

## 本次修复方式

为避免第三方 primitive 在 React 19 下继续触发循环更新，本次将以下组件替换为仓库内可控的轻量实现：

- `BillNote_frontend/src/components/ui/switch.tsx`
- `BillNote_frontend/src/components/ui/checkbox.tsx`

要求：

- 保留现有 `checked`
- 保留 `defaultChecked`
- 保留 `onCheckedChange`
- 保留 `onClick`
- 不改业务调用点

也就是说，业务代码继续按原来的方式使用组件，但底层实现不再依赖当前有兼容性问题的 Radix primitive。

## 回归保护

修复以后，至少要保留两层保护：

### 1. 页面级冒烟测试

当前用例：

- `BillNote_frontend/tests/smoke/batch-selection.spec.ts`

它防止“页面能编译，但真实点击一轮就崩”的问题重新出现。

### 2. 轻量源码守卫

当前守卫：

- `BillNote_frontend/src/components/ui/ref-forwarding.test.js`
- `BillNote_frontend/src/components/ui/switch.test.js`

当前检查点包括：

- 组件仍使用稳定的 `forwardRef`
- `switch.tsx` 不再直接依赖 `@radix-ui/react-switch`
- `checkbox.tsx` 不再直接依赖 `@radix-ui/react-checkbox`

## 常见坑

### 1. 3015 端口已经有旧的 Vite 进程

如果冒烟测试结果和你刚改的代码对不上，先看是不是复用了旧 dev server。

检查：

```bash
lsof -nP -iTCP:3015 -sTCP:LISTEN
```

必要时清理：

```bash
kill <pid>
```

或者：

```bash
lsof -nP -iTCP:3015 -sTCP:LISTEN | awk 'NR>1 {print $2}' | xargs -r kill
```

### 2. 只看测试超时，不看浏览器异常

比如 “第二条视频点不到” 这种超时，不一定是定位器写错了，更可能是前面一步已经把页面打崩了。

### 3. 只修 smoke，不留源码级守卫

如果只保留页面测试，后面有人把有问题的 primitive 引回去，通常要等跑完整条用例才会发现。加一层轻量源码守卫更稳。

## 后续新增交互问题时的复用方式

下次遇到新的前端交互问题，建议复制当前 smoke 用例并改最小必要部分：

1. 保留 `page.route` 的 mock 框架
2. 只替换当前页面需要的接口数据
3. 保留 `pageerror` / `console error` 收集
4. 把用户操作路径改成新问题对应的点击链路
5. 最后断言用户可见结果，而不是只断言内部 state

## 本次相关文件

- `BillNote_frontend/playwright.config.ts`
- `BillNote_frontend/tests/smoke/batch-selection.spec.ts`
- `BillNote_frontend/src/components/ui/switch.tsx`
- `BillNote_frontend/src/components/ui/checkbox.tsx`
- `BillNote_frontend/src/components/ui/ref-forwarding.test.js`
- `BillNote_frontend/src/components/ui/switch.test.js`

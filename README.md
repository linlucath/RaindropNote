# 雨滴笔记助手

雨滴笔记助手是一款面向个人学习、研究和内容整理场景的 AI 视频笔记工具。它可以将用户有权访问和使用的视频、音频或本地文件整理为可检索、可校对、可沉淀的 Markdown 文字稿与结构化笔记。

项目采用 FastAPI 后端、React + Vite 前端，并支持可选的 Tauri 桌面端打包。

## 定位

雨滴笔记助手关注的是“把已经合法获得的学习材料整理成自己的知识资产”，而不是下载器、搬运工具或内容分发服务。

- 适合：课程复盘、会议材料整理、公开讲座学习、个人收藏内容归档、本地音视频转写。
- 不适合：绕过平台限制、批量抓取第三方内容、复制传播未经授权的视频/字幕/文字稿。

## 功能特性

- 多来源内容导入：支持常见公开视频链接与本地音视频文件。
- AI 文字稿整理：将转写结果校对为更易阅读的 Markdown 文本。
- 结构化笔记生成：根据内容生成重点、章节、摘要和可继续编辑的学习笔记。
- 自定义模型配置：支持 OpenAI、DeepSeek、Qwen 等兼容模型服务。
- 多种转写引擎：支持 Fast-Whisper、MLX-Whisper、Groq、BCut 等方案。
- 历史记录管理：保留生成记录，方便回看、收藏和继续整理。
- 原文参照：支持查看分段转写内容，便于核对和修订。
- 本地优先部署：可通过源码、Docker 或桌面端方式运行。

## 使用边界

请只处理你拥有权利、已经获得授权，或平台规则允许你用于个人学习和整理的内容。使用者应自行确认内容来源、平台条款和版权边界。

请勿将本项目用于：

- 绕过平台访问控制、会员限制、付费限制或其他技术保护措施。
- 批量抓取、复制、存储、传播第三方平台内容。
- 公开分发未经授权的视频、音频、字幕、全文文字稿或衍生材料。
- 以任何方式暗示本项目与第三方平台存在官方合作、授权或背书。

生成结果可能包含识别错误或模型幻觉，请在引用、发布或用于正式场景前自行核验。

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

后端默认监听 `0.0.0.0:8483`。

### 前端

```bash
cd BillNote_frontend
pnpm install
pnpm dev
```

前端开发服务默认运行在 `http://localhost:3015`，并将 `/api` 代理到后端。

### Docker

```bash
docker-compose up
```

如需 GPU 版本：

```bash
docker-compose -f docker-compose.gpu.yml up
```

## 环境依赖

### FFmpeg

项目依赖 FFmpeg 进行音频处理与转码。源码部署时请先安装：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

Windows 用户可从 [FFmpeg 官网](https://ffmpeg.org/download.html)下载安装，并将其加入系统环境变量 `PATH`。

### 模型与 API Key

大模型服务和转写服务可在应用设置页中配置。建议优先使用你可控、合规、稳定的模型服务。

## 项目结构

- `backend/`：FastAPI 后端、下载适配、转写、笔记生成、数据库与导出逻辑。
- `BillNote_frontend/`：React + Vite 前端，包含主工作区、设置页、历史记录和收藏页。
- `nginx/`：Docker Web 部署的 Nginx 配置。
- `docs/`：开发说明、运行手册与历史设计文档。

## 开发命令

```bash
# 后端
cd backend
python main.py

# 前端
cd BillNote_frontend
pnpm dev
pnpm build
pnpm lint
```

## 许可证

MIT License

## 致谢

本项目中的部分平台适配逻辑参考了公开社区项目与文档。请在使用相关功能时遵守对应平台规则和内容版权要求。

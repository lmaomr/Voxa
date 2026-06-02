# 🎙️ Voxa

**AI 语音工具包 · AI Voice Toolkit**

语音克隆 · 语音识别 · 人声分离 · 翻译 · 视频翻译 · YouTube 下载

---

## 🇨🇳 中文文档

### 简介

Voxa 是一个基于 FastAPI 的全栈 AI 语音工具包。

### 核心功能

| 功能              | 说明                                                | 技术栈            |
| ----------------- | --------------------------------------------------- | ----------------- |
| 🎤 语音克隆 (TTS) | 给定参考音频和文本，克隆音色生成语音                | VoxCPM2           |
| 📝 语音识别 (ASR) | 多语言语音转文字，支持词级对齐                      | WhisperX          |
| 🔊 人声分离       | 将音频拆分为人声和伴奏                              | UVR5              |
| 🌐 文本翻译       | 80+ 种语言，多后端自动切换                          | Bing/Baidu/Google |
| 🎬 视频翻译       | 端到端管线：提取→分离→ASR→翻译→克隆→混音→压制 | 以上全部组合      |
| 📥 YouTube 下载   | 下载 YouTube 视频                                   | yt-dlp            |

### 快速开始

`ash python -m venv .venv .venv\Scripts\activate pip install -e . uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload `

### API 端点

| 方法 | 端点                          | 说明         |
| ---- | ----------------------------- | ------------ |
| POST | /api/v1/tts/clone             | 语音克隆     |
| POST | /api/v1/asr/transcribe        | 语音识别     |
| POST | /api/v1/audio/separate        | 人声分离     |
| POST | /api/v1/translate/translate   | 文本翻译     |
| POST | /api/v1/video/video-translate | 视频翻译     |
| POST | /api/v1/youtube/info          | YouTube 信息 |
| POST | /api/v1/youtube/download      | YouTube 下载 |
| POST | /api/v1/upload/upload         | 文件上传     |

### 项目结构

`Voxa/ ├── app/ │   ├── main.py              # FastAPI 入口 │   ├── api/v1/endpoints/    # API 端点（8个模块） │   ├── services/            # AI 服务层（6个服务） │   ├── core/                # 配置 + 安全 │   ├── models/              # SQLAlchemy 数据模型 │   ├── schemas/             # Pydantic 数据模式 │   └── crud/                # 数据库操作 ├── static/index.html        # Web UI ├── models/                  # AI 模型文件 ├── data/                    # 上传文件 + 输出 └── tests/                   # 测试`

### 许可证

MIT License

---

## 🇬🇧 English Documentation

### Overview

Voxa is a full-stack AI voice toolkit built on FastAPI.

### Core Features

| Feature                     | Description                          | Tech Stack        |
| --------------------------- | ------------------------------------ | ----------------- |
| 🎤 Voice Cloning (TTS)      | Clone voice from reference audio     | VoxCPM2           |
| 📝 Speech Recognition (ASR) | Multi-language STT                   | WhisperX          |
| 🔊 Vocal Separation         | Split audio into vocals/instrumental | UVR5              |
| 🌐 Text Translation         | 80+ languages                        | Bing/Baidu/Google |
| 🎬 Video Translation        | End-to-end translation pipeline      | All of the above  |
| 📥 YouTube Download         | Download YouTube videos              | yt-dlp            |

### Quick Start

`ash python -m venv .venv source .venv/bin/activate pip install -e . uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload `

### API Endpoints

| Method | Endpoint                      | Description        |
| ------ | ----------------------------- | ------------------ |
| POST   | /api/v1/tts/clone             | Voice cloning      |
| POST   | /api/v1/asr/transcribe        | Speech recognition |
| POST   | /api/v1/audio/separate        | Vocal separation   |
| POST   | /api/v1/translate/translate   | Text translation   |
| POST   | /api/v1/video/video-translate | Video translation  |
| POST   | /api/v1/youtube/info          | YouTube info       |
| POST   | /api/v1/youtube/download      | YouTube download   |
| POST   | /api/v1/upload/upload         | File upload        |

### License

MIT License

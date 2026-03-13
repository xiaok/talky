# Talky（中文）

![Talky Banner](assets/github-banner.png)

Talky 是一个面向 macOS（Apple Silicon）的本地语音输入助手。  
它采用按住说话的交互方式，在本地完成 ASR + LLM 处理，并将整理后的文本输出到当前应用。

**语言 / Language:** [English](README.md) | 中文

### 1）产品卖点与核心操作流程

**产品卖点**
- 全本地链路：ASR + LLM 均在本机运行。
- 交互简单：按住说话，松开即处理并粘贴。
- 兜底明确：无可用焦点时自动弹出悬浮复制面板。
- 自动归档：每日历史保存在 `history/YYYY-MM-DD.md`。

**核心操作流程**
1. 按住热键开始录音。
2. 松开后进行转写（ASR）。
3. 本地模型清理与结构化文本（LLM）。
4. 自动粘贴到当前输入框（无焦点则走复制面板）。

### 2）安装前检查 Checklist

首次运行前请确认：

- `python3 --version` 可用
- `ollama --version` 可用
- `ollama list` 至少有一个本地模型
- 磁盘剩余空间 >= 10GB
- 网络可访问 PyPI 和 Hugging Face
- 可选加速：
  ```bash
  export HF_TOKEN=你的token
  ```

一键自检命令：

```bash
python3 --version && ollama --version && ollama list && \
echo "Disk free:" && df -h .
```

若未安装模型：

```bash
ollama pull <your-model>
```

### 3）首次安装与后续使用（命令行分步引导）

先手动安装前置依赖：
- Python 3
- Ollama（https://ollama.com/download）

#### 首次安装

```bash
cd /path/to/talky
chmod +x start_talky.command
./start_talky.command
```

然后在 macOS 中授权：
- `系统设置 -> 隐私与安全性 -> 麦克风`
- `系统设置 -> 隐私与安全性 -> 辅助功能`

启动后操作：
1. 按住热键说话。
2. 松开等待处理。
3. 确认文本已粘贴到目标输入框。

#### 后续日常使用

```bash
cd /path/to/talky
./start_talky.command
```

说明：
- 无需重复执行 `chmod +x`。
- 启动时会先检查远端更新，有新版本会自动快进更新后再启动。

#### 快速故障排查

若 Whisper 模型下载中断/损坏：

```bash
rm -rf local_whisper_model
source .venv/bin/activate
python download_model.py
./start_talky.command
```

若 Ollama 预热出现 `502`：

```bash
pkill ollama
ollama serve
```

### 4）愿景

Talky 的目标是让语音输入在高频开发和写作场景中真正可用：
- 更私密：本地计算，不上传云端
- 更干净：自动清理口语冗余，输出可直接使用
- 更顺手：跨应用输入链路尽量无感

它是一个聚焦实用性的本地助手，帮助你更快地从“想法”进入“表达”。

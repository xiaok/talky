# Talky（中文）

![Talky Banner](assets/github-banner.png)

Talky 是一个面向 macOS（Apple Silicon）的本地语音输入助手。  
它采用按住说话的交互方式，在本地完成 ASR + LLM 处理，并将整理后的文本输出到当前应用。

**语言 / Language:** [English](README.md) | 中文

Logo 文件：[`assets/talky-logo.png`](assets/talky-logo.png)

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
- （部分机器）已安装 `ffmpeg`，用于音频解码兼容
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

### 3）操作指引（默认：本地大模型）

先手动安装前置依赖：
- Python 3
- Ollama（https://ollama.com/download）

#### A）本地大模型（Talky 与 Ollama 在同一台 Mac）

Part 1（一次性）：系统依赖 + 环境准备 + Whisper 模型下载

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
brew install ffmpeg

cd /path/to/talky
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 download_model.py
```

若你使用 SOCKS 代理并出现 `socksio` / 代理报错：

```bash
pip install "httpx[socks]"
```

若你通过代理下载模型，可在下载前设置：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_TOKEN=你的token
export all_proxy=socks5://127.0.0.1:7897
python3 download_model.py
```

Part 2（一次性）：首次启动

```bash
cd /path/to/talky
chmod +x start_talky.command
./start_talky.command
```

Part 3（日常）：一键切回本地模式并自动重启

```bash
cd /path/to/talky
./start_talky.command --remote "http://127.0.0.1:11434" --model "qwen3.5:9b" --restart
```

Part 4：成功信号
- `mode: local`
- `Using Ollama model: ...`
- `ASR elapsed`、`LLM elapsed`、`Final text`

如果你使用局域网连接其他设备的大模型，请查看 [局域网大模型流程（LAN Ollama）](LAN_OLLAMA_GUIDE.zh.md)。

可选启动器 App：
- 仓库已提供 `talky_launcher.applescript` 模板。
- 将其中 `set scriptPath to "/path/to/start_talky.command"` 改为你本机路径。
- 用 Script Editor 导出为 App 后，可固定到 Dock 使用。

然后在 macOS 中授权：
- `系统设置 -> 隐私与安全性 -> 麦克风`
- `系统设置 -> 隐私与安全性 -> 辅助功能`

启动后操作：
1. 按住热键说话。
2. 松开等待处理。
3. 确认文本已粘贴到目标输入框。

说明：
- 无需重复执行 `chmod +x`。
- 启动时会先检查远端更新，有新版本会自动快进更新后再启动。
- `start_talky.command` 在启动前会清理代理变量，以保证本地 Ollama 连接稳定。
- 若你所在网络必须代理下载模型，请按“本地 Step 1”先手动执行 `download_model.py`。
- 局域网模式下，Talky 会跳过本机 `ollama serve` 启动步骤，直接连接配置的远端地址。
- 首次引导：若尚未配置 host 且本地 Ollama 不可用/无模型，启动时会先让你选择本地或远端地址，再继续模型检查。

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

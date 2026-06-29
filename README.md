# XMUOJ Auto Answer

XMUOJ 自动答题工具。登录 → 读题 → AI 解题 → 提交 → 判题，全流程自动化。

## 快速开始

**前置：** 安装 [Python 3.10+](https://www.python.org/downloads/)（勾选 Add to PATH）

**1.** 下载 [xmuoj_auto.zip](xmuoj_auto.zip) 解压

**2.** 双击 `启动.bat`

首次运行自动安装依赖、下载浏览器，然后引导输入凭据。之后每次只需粘贴比赛网址即可。

## 使用方式

```
  粘贴比赛网址: https://xmuoj.com/contest/361

  选题方式:
   [1] 全部题目
   [2] 指定区间（如 12-30）
   [3] 指定题目（如 JD027,JD029）
   [4] 只做前N题

  输出语言:
   [1] C++ (默认)    [2] C    [3] Python3    [4] Java

  延时设置（防封号）:
   [1] 快速    [2] 正常    [3] 安全

  回车开始 →
```

也支持命令行：

```bash
python run.py -c 361 -r 27-40 -l python -d 8
```

## 支持的 AI 模型

所有 OpenAI 兼容接口均可。在 `.env` 中配置：

```ini
API_KEY=sk-xxx
API_BASE=https://api.deepseek.com/v1     # DeepSeek / Kimi / Qwen / GPT / ...
API_MODEL=deepseek-v4-pro
```

| 厂商 | API_BASE |
|------|----------|
| DeepSeek | `https://api.deepseek.com/v1` |
| Kimi | `https://api.moonshot.cn/v1` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| OpenAI | `https://api.openai.com/v1` |

## 文件结构

```
├── 启动.bat            # 双击启动，自动检测环境
├── start.py            # 交互式启动器
├── run.py              # 命令行入口
├── setup_check.py      # 环境自检，自动安装依赖
├── orchestrator.py     # 主调度器
├── auth.py             # Playwright 登录
├── fetcher.py          # API 题目获取
├── ai_solver.py        # AI 代码生成（Anthropic + OpenAI）
├── submit_engine.py    # 提交 + 判题
├── config.py           # 配置
└── .env.example        # 凭据模板
```

## License

MIT

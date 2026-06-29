# XMUOJ Auto Answer

XMUOJ 自动答题工具 — 登录 → 读题 → AI 解题 → 提交 → 判题，全流程自动化。

## 快速开始

### 1. 安装依赖

```bash
pip install playwright beautifulsoup4 anthropic
playwright install chromium
```

### 2. 获取 API Key

本工具使用 **DeepSeek** 生成代码（费用约 1 元/200 题）。

1. 打开 [platform.deepseek.com](https://platform.deepseek.com)
2. 注册 → API Keys → 创建密钥
3. 复制 `sk-...` 开头的密钥

### 3. 启动

```bash
python start.py
```

首次运行会引导输入 XMUOJ 凭据和 DeepSeek 密钥，之后保存在 `.env` 自动复用。

也可以直接创建 `.env` 文件：

```ini
XMUOJ_USERNAME=你的学号
XMUOJ_PASSWORD=你的密码
XMUOJ_CONTEST_PASSWORD=ilovexmu
DEEPSEEK_API_KEY=sk-你的密钥
```

## 使用方式

### 交互模式（推荐）

```bash
python start.py          # 或双击 启动.bat
```

按提示输入比赛网址和选题方式，全程引导式操作。

### 命令行模式

```bash
python run.py --contest 362 --limit 2                         # 前 N 题
python run.py --contest 361 --range 12-30                     # 区间
python run.py --contest 361 --problems JD027,JD029,7318       # 指定题目
```

## 效果

```
=====================================================
  XMUOJ AUTO ANSWER
  Contest: 361 | Model: deepseek-v4-pro
=====================================================
  [1/15] JD027: 怪兽辨识
    Attempt 1 → Accepted | Score: 100 | Time: 2ms
  OK | Score: 100 | Attempts: 1

  [2/15] JD028: 田赋计算
    Attempt 1 → Accepted | Score: 100 | Time: 2ms
  OK | Score: 100 | Attempts: 1
  ...
=====================================================
  Solved: 14 | Failed: 1 | Success rate: 93.3%
=====================================================
```

## 支持平台

- 所有以 [QingdaoU/OnlineJudge](https://github.com/QingdaoU/OnlineJudge) 为底层的 OJ 平台
- 已测试：xmuoj.com

## 技术栈

- 浏览器自动化：Playwright（仅登录）
- API 调用：requests
- AI 引擎：DeepSeek V4 Pro（Anthropic SDK）
- 判题监控：API 轮询

## License

MIT

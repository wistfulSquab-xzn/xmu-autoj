# 新设备环境搭建

---

## 1. 安装 Python

Python 3.10+，安装时勾选「Add to PATH」。

## 2. 安装依赖

```powershell
pip install playwright beautifulsoup4 anthropic
playwright install chromium
```

## 3. 获取 DeepSeek API 密钥

1. 打开 https://platform.deepseek.com
2. 注册账号 → API Keys → 创建新密钥
3. 复制 `sk-...` 开头的密钥

> 费用极低：约 0.5 元/百万 token，100 道题 ≈ 几毛钱

## 4. 启动

```powershell
cd xmuoj_auto
python start.py          # 或双击 启动.bat
```

首次运行会引导输入：
- XMUOJ 学号、密码、比赛密码
- DeepSeek API 密钥

之后凭据保存在 `.env` 文件，下次直接启动即可。

---

## 不需要 Claude Code

本工具独立运行，不依赖 Claude Code。AI 调用直接通过 DeepSeek API。

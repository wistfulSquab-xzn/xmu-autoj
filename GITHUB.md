# GitHub 发布教程

---

## 一、安装 Git

### 1. 下载

打开 https://git-scm.com/download/win ，会自动下载安装包。

### 2. 安装

双击安装包，一路点「Next」用默认选项即可。**需要注意的两页**：

| 步骤 | 选项 | 截图说明 |
|------|------|---------|
| 选择编辑器 | 选 **Nano** 或保留默认 Vim | 新手推荐 Nano |
| 调整 PATH | 选 **Git from the command line** | 让终端能识别 git 命令 |
| 行尾转换 | 选 **Checkout Windows-style, commit Unix-style** | 默认推荐项 |

其余全部点 Next → Install。

### 3. 验证

安装完成后，**关闭所有终端窗口，重新打开一个**，输入：

```powershell
git --version
```

看到 `git version 2.xx.x` 即成功。

### 4. 配置用户名

```powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

---

## 二、注册 GitHub

1. 打开 https://github.com
2. 点右上角 **Sign up**
3. 输入邮箱、密码、用户名
4. 验证邮箱
5. 登录

---

## 三、创建仓库

1. 登录 GitHub 后，点右上角 **+** → **New repository**

2. 填写信息：

   | 字段 | 填写 |
   |------|------|
   | Repository name | `xmuoj-auto` |
   | Description | `XMUOJ 自动答题挂机工具` |
   | Public / Private | 选 **Private**（私有） |
   | Initialize with README | **不要勾选** ❗ |
   | Add .gitignore | **不要勾选** |
   | Add a license | **不要勾选** |

3. 点 **Create repository**

4. 创建后会跳转到一个页面，**复制那三行命令**（以 `git remote add origin` 开头的），备用。

---
git remote add origin https://github.com/xzn-xmu/xmu-autoj.git
git branch -M main
git push -u origin main

## 四、推送代码

打开 PowerShell，逐行执行：

```powershell
# 进入工程目录
cd e:\Code_Workspace\xmuoj_auto

# 初始化 Git 仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "🎉 首次提交"

# 关联远程仓库（换成你自己的地址）
git remote add origin https://github.com/你的用户名/xmuoj-auto.git

# 推送
git branch -M main
git push -u origin main
```

推送时会弹窗让你登录 GitHub，选 **Sign in with browser**，浏览器确认即可。

---

## 五、验证

刷新 GitHub 网页，应该能看到所有文件了。

---

## 六、后续更新代码

改完代码后：

```powershell
cd e:\Code_Workspace\xmuoj_auto

git add .
git commit -m "描述你改了什么"
git push
```

三行命令，30 秒完成。

---

## 注意事项

- `.env` 文件**不会被上传**（已在 `.gitignore` 排除），API 密钥不会泄露
- 建议仓库设为 **Private**（私有），仅自己可见
- 如果要公开，确认 `.env` 不在仓库中

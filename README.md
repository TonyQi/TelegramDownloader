# Telegram Downloader

一个基于 PySide6 和 Telethon 的 Telegram 桌面客户端。它保留类似 Telegram 客户端的会话浏览、消息查看和发送能力，并额外增强了文件下载能力：任务队列、并发分块、暂停/继续、取消和断点续传。

## 功能

- Telegram 二维码登录，Session 持久化
- 会话列表和消息浏览
- 文本消息发送
- 图片、视频、相册消息预览
- 历史消息向上滚动分页加载
- 右键文件消息或相册消息加入下载队列
- 下载队列二级页面
- 多任务并发下载
- 单文件分块并发下载
- 断点续传
- 暂停、开始、继续、取消任务
- 下载进度、速度和错误信息显示
- SOCKS5 / HTTP 代理配置
- 代理连通 Telegram 测试
- PyInstaller 打包 exe

## 环境

建议使用 Python 3.10 或更高版本。

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

Telegram API 信息仍在 `config.py` 中：

- `API_ID`
- `API_HASH`

代理、下载目录、任务并发数、分块并发数可以在应用内 `Settings` 页面设置。配置会保存到：

```text
data/settings.json
```

代理支持：

- SOCKS5
- HTTP
- 可选用户名和密码
- 可测试是否能连接 Telegram

## 启动

```bash
python main.py
```

首次启动会弹出二维码登录窗口。使用 Telegram 手机客户端扫码登录后，即可进入主界面。

## 使用

### 聊天

- 左侧选择会话
- 中间查看消息
- 底部输入框发送文本消息
- 向上滚动加载更早消息
- 图片、视频和相册会先显示占位，再后台加载预览图

### 下载

- 在文件、图片、视频或相册消息上右键
- 点击 `Download`
- 程序会切换到 `Downloads` 页面
- 在下载页面管理任务：`Start`、`Pause`、`Resume`、`Cancel`

也可以在 `Downloads` 页面粘贴 Telegram 消息链接手动添加下载任务。

## 打包为 exe

项目提供了 PyInstaller 打包脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

打包完成后可执行文件位于：

```text
dist\TelegramDownloader\TelegramDownloader.exe
```

当前采用文件夹模式打包，适合 PySide6 桌面程序，启动更稳定。

## 目录说明

```text
core/          配置、数据库、代理
downloader/    下载队列、分块下载、断点续传
models/        任务模型
telegram/      Telegram 登录、会话、消息、媒体接口
ui/            PySide6 界面
data/          配置和任务数据库
sessions/      Telegram 登录会话
downloads/     默认下载目录
```

## 注意

- 修改代理后，建议重新登录或重启应用，让新的代理配置完全生效。
- 打包后的程序首次运行也需要扫码登录。
- `sessions/` 中保存登录会话，不建议分享给他人。

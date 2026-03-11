# Telegram Desktop Downloader

桌面版 Telegram 下载器，支持：

- 二维码登录
- Session 持久化
- 固定代理
- 根据 Telegram 消息链接下载 document 文件
- 多个文件同时下载
- 单文件分块并发下载
- 断点续传
- 暂停 / 继续 / 取消
- 进度和速度显示
- “同时下载任务数”在程序内可设置

## 安装

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.py`：

- `API_ID`
- `API_HASH`
- `GLOBAL_PROXY`

## 启动

```bash
python main.py
```

## 使用

首次启动会弹出二维码登录窗口。登录成功后，在主界面输入 Telegram 消息链接即可下载。

## 说明

当前版本重点支持消息中的 `document` 类型资源。

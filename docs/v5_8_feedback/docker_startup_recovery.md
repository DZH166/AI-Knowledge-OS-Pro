# Windows Docker 启动兼容处理（2026-09-06）

## 实测结论

Docker Desktop 4.77.0 在清理 `dockerInference` 时失败。升级至有对应修复说明的 4.89.0 后，已有不可访问端点仍需要隔离；随后通过 Docker 内置 restart 实测，又遇到新 `sailor-ingest.sock` 的同类错误。因此不能宣称版本更新已经根治本机 Windows 26200 的兼容问题。

修复过程中没有恢复出厂设置、清空容器、删除镜像/数据卷、注销用户 WSL 发行版或重启 Windows。原有数据盘位置不变；升级后补齐了原有 D 盘 Docker 目录下缺失的 `main` 运行目录。

当前安装版本：Docker Desktop 4.89.0.238018；引擎 29.7.2。更新通过官方 CLI 执行，缓存安装包的 Docker Inc 数字签名有效。官方资料：

- [Docker 4.89.0 更新说明](https://docs.docker.com/desktop/release-notes/#4890)
- [同类 Windows 临时端点故障报告](https://github.com/docker/desktop-feedback/issues/460)

## 安全启动入口

实现位于 `scripts/windows/start_docker_safely.ps1`。它是本地兼容处理，不是 Docker/Windows 内部修复，也不会自动安装到其他机器。

- 使用互斥锁防止两个安全入口同时处理目录。
- 显式检查本机 Linux 引擎的 Windows 管道，不跟随远端 context；连接覆盖变量只在探测子进程中移除。健康时不停止或重启引擎。
- 有进程时，必须先确认最新 backend 启动后产生的错误文件包含已知通信端点故障。未知故障、正在启动或过时错误记录都拒绝强制操作。
- 仅停止路径经过核对的 Docker 自身进程；命令有超时，不停止其他 WSL 工作区。
- 临时父目录必须是普通目录，子项必须全部是白名单内的零字节通信端点。出现普通文件、未知名字或目录联接就拒绝处理。
- 仅改名备份 `Docker/run` 和 `docker-secrets-engine`，不递归删除、不访问容器数据盘。备份名称为 `*.safe-start-时间戳`，保持可恢复。
- 启动后必须收到引擎版本响应才记为成功；日志位于 `%LOCALAPPDATA%/DockerSafeStart/last-start.log`。

本机安装副本在 `%LOCALAPPDATA%/DockerSafeStart/start_docker_safely.ps1`，桌面的 `Docker Desktop.lnk` 指向该入口。原快捷方式备份为同目录 `Docker Desktop.original-20260906.lnk`。使用当前已有的 PowerShell 7 运行时；没有设置 ExecutionPolicy Bypass，也没有修改系统脚本执行策略。其他机器应先确认本机 PowerShell 7 路径及 Docker 安装位置，不能直接照搬快捷方式。

## 验证与边界

- 从已知崩溃恢复后引擎正常响应。
- `-CheckOnly` 只检查、不执行恢复；外部同时设置不存在的 context 和不可达 DOCKER_HOST 时，仍正确识别健康本机引擎。没有修改用户的连接配置。
- 两次正常退出后通过安全入口冷启动成功，其中一次实际启动桌面快捷方式。
- 原 8 个容器的 ID/名称与 8 个数据卷名称前后完全一致。
- 正常退出命令：`docker desktop stop --timeout 45`。重新打开请使用桌面安全入口，不使用仍会复发的 Docker 内置 Restart。

尚未证明：强制断电后的所有状态、系统重启后的内核行为、其他 Windows 版本、未来 Docker 版本。若新版改变端点名，脚本会拒绝自动处理，需要重新核对，而不是放宽成任意目录删除。备份不会自动清理；只有核对后才考虑人工回收。

# 部署与“无终端”选项

普通浏览器页面不能安装/启动本地程序，也不能直接打开 S7comm 的 TCP 102。因此网页始终需要一个本地或远端的 WebSocket 网关。下面按用户操作复杂度排列。

## A. 双击启动器（默认，需要 Python）

项目根目录：

- Windows：双击 `start_twin.bat`
- Linux：双击 `start_twin.desktop`

首次会创建 `.venv`、安装 `requirements.txt`，然后启动页面 + 网关并打开浏览器。用户不需要输入命令，但机器上必须有 Python 3.10+，且会有一个终端/控制台窗口（关闭它即停止服务）。

## B. Windows 单文件 exe（最终用户无需 Python / 终端）

构建（开发者在一台 Windows 构建机做一次）：

1. 确认构建机有 Python 3.10+。
2. 在项目根目录双击 `build_exe.bat`。
3. 产物：`dist\TIAWebTwin.exe`。
4. 把 exe 发给最终用户；双击即可，exe 内已带 Python、依赖、网关、网页与 manifest。

运行时：

- 打开一个小的 Tk 控制窗口（可“打开页面/退出”），不需要控制台。
- 页面与网关在同一个进程内；页面默认离线，点“连接 PLC”输入 PLCSIM Advanced 地址。
- 关闭控制窗口即停止，端口自动释放。

注意：

- exe 打包的是构建时的 manifest 和页面；改了 tag/地址后需要重新构建。
- 构建文件见 `desktop_app.py`、`tia_twin.spec`；PyInstaller 的 snap7 二进制由 spec 的 `collect_all('snap7')` 收集。
- 未签名的 exe 可能触发 Windows SmartScreen；正式分发请做代码签名。
- 2D/3D 项目都能打包；spec 会自动收集存在的 `vendor/`。

## C. Windows 服务 / 远端网页（浏览器在另一台机器）

适用于“网页在另一台电脑，网关常驻 PLCSIM 所在 Windows”：

1. 在 PLCSIM 所在机器把 `tia_gateway.py --wait-plc` 安装成 Windows 服务（例如 NSSM），开机自启。
2. 页面静态托管在任意 HTTP 服务上；页面在线模式填写 PLC 地址，网关地址由页面/启动参数提供。
3. 网关必须设置 Token，限制防火墙来源；不要暴露到公网。

这个模式需要管理员安装一次服务，但之后浏览器端不需要任何本地程序。

## 不能做的事

- 不能靠网页静默安装/启动 Python 网关；
- 不能从浏览器直连 TCP 102/S7comm；
- 不要把 8765 无 Token 暴露到公网。

这是仿真/教学工具，不替代安全回路。

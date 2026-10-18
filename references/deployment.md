# 部署与“无终端”选项

普通浏览器页面不能直接打开 S7comm 的 TCP 102。因此网页始终需要一个本地或远端的 WebSocket 网关。下面按用户操作复杂度排列。

## A. 双击启动器（默认零命令 · 最推荐）

项目根目录已预置全套免命令行启动器（纯 7-bit ASCII，100% 兼容 Windows 11 24H2）：

- **Windows 用户**：
  - **`start.bat`**：双击即可启动。自动智能寻找真实 Python（避开 WindowsApps 劫持）、启动静态服务与网关，并自动唤起默认浏览器。关闭黑窗口即退出。
  - **`make_shortcut.bat`**：双击一次，使用原生 PowerShell 在 Windows 桌面上创建【TIA Web 3D Twin】桌面快捷方式，后续在桌面双击即可使用。
  - **`start_silent.bat`**：后台静默启动。完全不弹出黑色 cmd 命令行窗口，3 秒后黑窗口自动消失，服务在后台常驻运行，浏览器可直接存为书签访问。
  - **`stop.bat`**：一键干净终止所有后台常驻服务进程。
- **Linux 用户**：双击 `start_twin.desktop`（首次可能需在文件管理器里允许执行）或执行 `./start_twin.sh`。

## B. 关于 Windows 单文件 exe 的安全限制说明

> [!WARNING]
> **Windows 11 24H2 安全机制限制（Smart App Control / Temp 目录拦截）**：
> PyInstaller 默认的单文件模式（`--onefile`）在运行时必须向系统 `%TEMP%` 临时目录动态解压二进制文件。在 Windows 11 24H2 下会触发 `Could not create temporary directory!` 的安全拦截。
> 因此：
> 1. **严禁在 Windows 11 上向用户分发 `--onefile` 单文件 exe！**
> 2. 交付首选 **`start.bat`** 或 **`make_shortcut.bat` 桌面图标**（启动速度最快、0 权限问题、无 DLL 解压开销）。
> 3. 若必须打包成可执行文件分发给无 Python 的电脑，在 `tia_twin.spec` 中必须使用 `--onedir`（便携文件夹免解压模式），打包出整个目录分发，不得依赖单文件 Temp 释放。

## C. Windows 服务 / 远端网页（浏览器在另一台机器 / 车间平板）

适用于“网页在另一台电脑，网关常驻 PLC 所在工控机”：

1. 在工控机双击 `start_silent.bat`，或把 `run_twin.py --no-browser` 注册为 Windows 服务开机自启。
2. 局域网内的任何电脑或车间平板，直接在浏览器输入：
   `http://[工控机局域网IP]:8000/?ws=ws%3A%2F%2F[工控机局域网IP]%3A8765%2Fws`
3. 页面在线模式选择目标 PLC 即可实时监视。
4. 网关必须设置 Token，限制防火墙来源；不要暴露到公网。

## 不能做的事

- 不能靠网页静默安装/启动 Python 网关；
- 不能从浏览器直连 TCP 102/S7comm；
- 不要把 8765 无 Token 暴露到公网；
- 严禁在非系统盘创建跨盘符 `.venv`（会导致 `_ctypes.pyd` DLL 初始化失败）；
- 严禁使用 `.vbs` 脚本（Win11 24H2 已彻底废除 VBScript 引擎）。

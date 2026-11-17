# 进销存管理系统

一个面向中小型企业的进销存管理系统，提供本地桌面端和服务器部署端。项目采用 Python + FastAPI + SQLite + Tkinter 实现，适合课程实训、局域网演示和二次开发。

## 功能

- 基础资料：用户、供应商、客户、商品管理
- 采购管理：采购入库、采购退货、采购信息查询
- 销售管理：销售出库、客户退货、销售信息查询
- 库存管理：库存查询、商品借出、商品归还、借还记录查询
- 系统管理：用户角色、权限设置、密码修改、数据备份与恢复
- 经营报表：销售、采购、库存、借还统计及 CSV 导出
- 两种运行方式：单机本地模式、服务器 API + 远程桌面客户端模式

## 项目结构

```text
app/                    FastAPI 服务端、数据库和业务逻辑
app/routers/            认证、基础资料、交易、库存、报表等 API 路由
client/                 Tkinter 桌面客户端和 API 客户端
tests/                  API 自动化测试
run_server.py           启动服务器端 API
run_local.py            启动本地 API 并打开桌面客户端
requirements.txt        Python 依赖
```

## 环境要求

- Python 3.11 或更高版本（建议 3.13）
- Windows 运行桌面客户端需要 Tkinter（官方 Python 安装包通常已包含）

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 本地桌面模式

本地模式会自动启动回环地址 API，并打开桌面登录窗口。数据库默认保存在当前用户的本地应用数据目录，不会写入代码仓库。

```powershell
python run_local.py
```

默认登录账号：

- 账号：`admin`
- 密码：`admin123`

首次演示后建议立即修改管理员密码。也可以通过环境变量设置初始管理员密码：

```powershell
$env:IMS_ADMIN_PASSWORD = "your-strong-password"
python run_local.py
```

## 服务器模式

在服务器上启动 API：

```powershell
$env:IMS_MODE = "server"
$env:IMS_ADMIN_PASSWORD = "your-strong-password"
python run_server.py --host 0.0.0.0 --port 8000
```

远程桌面客户端连接服务器：

```powershell
python -m client.main --api http://服务器地址:8000
```

生产或演示环境建议通过防火墙只开放需要的端口，并使用独立的 `IMS_DATA_DIR` 保存服务端数据库：

```powershell
$env:IMS_DATA_DIR = "D:\\InventorySalesData"
```

## 数据位置

默认数据库路径由运行模式决定：

- Windows 本地模式：`%LOCALAPPDATA%\InventorySalesManagement\inventory.db`
- Windows 服务器模式：`%PROGRAMDATA%\InventorySalesManagement\inventory.db`
- 其他系统：使用用户目录下的应用数据目录

通过 `IMS_DATA_DIR` 可以覆盖默认位置。数据库、备份和运行日志均不应提交到 GitHub。

## 测试

```powershell
python -m compileall -q app client run_server.py run_local.py
python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v
```

## 打包发布

打包脚本位于仓库父目录，用于生成桌面客户端、远程客户端、服务端和安装器。发布包按项目约定输出到仓库外的 `项目发布包` 目录：

```powershell
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File .\构建打包.ps1 -Target all
```

如果只需要构建某一目标，可使用 `client`、`remote-client` 或 `server`。

## 安全提示

- 请勿把真实密码、生产数据库、备份文件或服务器地址密钥提交到公开仓库。
- 默认管理员密码仅用于首次演示，部署后必须修改。
- 服务器部署时请限制网络访问范围，并定期备份数据库。

## 许可证

当前仓库未指定开源许可证。如需公开分发，请根据项目实际情况补充合适的 `LICENSE` 文件。

@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ╔══════════════════════════════════════════╗
echo ║          Voxa - AI 语音工具包            ║
echo ║         正在启动服务器...                ║
echo ╚══════════════════════════════════════════╝
echo.

:: 设置 PyTorch 显存管理（减少碎片，避免 OOM）
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,expandable_segments:False

:: 检测虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo [✓] 检测到虚拟环境
    call .venv\Scripts\activate.bat
) else (
    echo [!] 未找到虚拟环境，尝试全局运行...
)

:: 检测依赖是否安装
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [!] 正在安装依赖...
    pip install -r requirements.txt
)

:: 打开浏览器（延迟3秒等服务器启动）
echo [*] 正在打开浏览器...
start http://localhost:8000/web/

:: 启动服务器
echo [*] 服务器启动中...
echo.
echo ╔══════════════════════════════════════════╗
echo ║    打开浏览器访问:                       ║
echo ║     http://localhost:8000/web/           ║
echo ║                                          ║
echo ║    按 Ctrl+C 停止服务器                  ║
echo ╚══════════════════════════════════════════╝
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

:: 如果服务器退出，暂停显示信息
echo.
echo 服务器已停止。
pause

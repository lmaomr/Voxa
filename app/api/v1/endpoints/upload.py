"""
文件上传 API
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, status

logger = logging.getLogger(__name__)
router = APIRouter()

# 上传文件保存目录
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm",
    ".mp4", ".avi", ".mov", ".mkv",
}

# 扩展名 → 类型标注
EXT_TYPE_HINT = {
    ".mp4": "视频", ".avi": "视频", ".mov": "视频", ".mkv": "视频",
    ".wav": "音频", ".mp3": "音频", ".flac": "音频",
    ".ogg": "音频", ".m4a": "音频", ".aac": "音频", ".webm": "音频",
}


@router.post("/upload", summary="上传文件（音频/视频）")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件到服务器

    支持格式: wav, mp3, flac, ogg, m4a, aac, webm（音频）
             mp4, avi, mov, mkv（视频）
    """
    # 检查文件格式
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}，支持的格式: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 保留原始文件名，如果重名则添加数字后缀
    original_stem = Path(file.filename).stem
    save_path = UPLOAD_DIR / file.filename
    counter = 1
    while save_path.exists():
        save_path = UPLOAD_DIR / f"{original_stem}_{counter}{ext}"
        counter += 1

    try:
        content = await file.read()
        save_path.write_bytes(content)
        logger.info(f"文件上传成功: {file.filename} -> {save_path} ({len(content)} bytes)")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败: {e}",
        )

    return {
        "status": "ok",
        "filename": file.filename,
        "path": str(save_path),
        "size": len(content),
        "web_url": f"/data/uploads/{save_path.name}",
    }


@router.get("/files", summary="列出已上传的文件")
async def list_uploaded_files():
    """列出所有已上传的音频文件"""
    files = []
    for f in sorted(UPLOAD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "web_url": f"/data/uploads/{f.name}",
            })
    return {"files": files}


@router.get("/out-files", summary="列出输出目录的文件")
async def list_output_files():
    """列出 data/out 目录下所有音频文件"""
    out_dir = Path("data/out")
    if not out_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(out_dir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            rel_path = f.relative_to(Path("data"))
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "web_url": f"/data/{rel_path.as_posix()}",
            })
    return {"files": files}

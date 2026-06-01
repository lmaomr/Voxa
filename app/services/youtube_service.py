"""
YouTube 视频下载服务 - 基于 yt-dlp
"""
import logging
import re
from datetime import datetime
from pathlib import Path

import yt_dlp
from PIL import Image, ImageFile

from app.core.config import settings

logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True


class YouTubeService:
    """YouTube 视频下载与信息提取服务"""

    def __init__(self):
        # 数据目录配置
        self._data_dir = Path(settings.DOWNLOAD_DIR).resolve()
        self._video_dir = self._data_dir / "videos"
        self._subtitle_dir = self._data_dir / "subtitles"
        self._thumbnail_dir = self._data_dir / "thumbnails"
        self._cookie_dir = self._data_dir / "cookies"

        # 确保目录存在
        self._video_dir.mkdir(parents=True, exist_ok=True)
        self._subtitle_dir.mkdir(parents=True, exist_ok=True)
        self._thumbnail_dir.mkdir(parents=True, exist_ok=True)
        self._cookie_dir.mkdir(parents=True, exist_ok=True)

    # ── 工具方法 ───────────────────────────────────────────────

    @staticmethod
    def _convert_to_jpg(input_path: str | Path) -> str | None:
        """将 WEBP/PNG 等格式的封面转换为 JPG，并清理文件名中的非法字符"""
        input_path = Path(input_path)
        if not input_path.exists():
            return None

        clean_name = re.sub(r'[\\/:*?"<>|]', '_', input_path.stem)
        output_path = input_path.parent / f"{clean_name}.jpg"

        if input_path.suffix.lower() in ['.jpg', '.jpeg'] and input_path == output_path:
            return str(input_path)

        try:
            with Image.open(input_path) as img:
                img = img.copy()
                if img.mode in ("RGBA", "P", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.convert("RGBA").split()[3])
                    background.save(output_path, 'JPEG', quality=95)
                else:
                    img.convert('RGB').save(output_path, 'JPEG', quality=95)
            logger.info(f"封面转换成功: {output_path.name}")
            return str(output_path)
        except Exception as e:
            logger.warning(f"封面转换失败: {e}")
            return None

    def _build_opts(self) -> dict:
        """构造 yt-dlp 下载选项"""
        opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": {
                "default": str(self._video_dir / "%(title)s.%(ext)s"),
                "thumbnail": str(self._thumbnail_dir / "%(title)s.%(ext)s"),
            },
            "postprocessor_args": {
                "merger": [
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-movflags", "faststart",
                ]
            },
            "noplaylist": True,
            "writethumbnail": True,
            "convertthumbnails": "jpg",
            "js_runtimes": {"node": {}},
            "remote_components": "ejs:github",
            "proxy": "http://127.0.0.1:7897",
            "verbose": False,
        }

        if opts["proxy"]:
            logger.info(f"使用代理: {opts['proxy']}")
            import os
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

        # 如果存在 cookie 文件则加载
        cookie_file = self._cookie_dir / "youtube_cookies.txt"
        if cookie_file.exists():
            opts["cookiefile"] = str(cookie_file)
            logger.info(f"使用 cookies: {cookie_file}")

        return opts

    # ── 核心方法 ───────────────────────────────────────────────

    def download(
        self,
        url: str,
        output_dir: str | Path | None = None,
    ) -> dict:
        """
        下载 YouTube 视频并提取信息

        Args:
            url: YouTube 视频 URL
            output_dir: 自定义输出目录（可选），None 则使用默认 data/videos

        Returns:
            {
                "title": "视频标题",
                "description": "视频描述",
                "upload_date": "2024年01月01日",
                "uploader": "上传者",
                "video_path": "视频本地路径",
                "subtitle_path": "字幕路径",
                "thumbnail_path": "封面 JPG 路径",
                "url": "原始 URL",
            }
        """
        logger.info(f"开始下载 YouTube 视频: {url}")

        ydl_opts = self._build_opts()

        # 如果指定了自定义输出目录
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            ydl_opts["outtmpl"]["default"] = str(output_dir / "%(title)s.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url)

            title = info.get("title", "unknown_title")
            description = info.get("description", "无描述")
            upload_date_str = info.get("upload_date", "20230101")
            upload_date = datetime.strptime(upload_date_str, '%Y%m%d')
            uploader = info.get("uploader", "未知上传者")

            # 获取下载后的视频本地路径
            video_path = ydl.prepare_filename(info)

            # 构建字幕路径（如果启用字幕下载）
            subtitle_path = str(self._subtitle_dir / f"{title}.zh-Hans.srt")

            # 封面处理：WEBP → JPG
            thumbnail_webp = str(self._thumbnail_dir / f"{title}.webp")
            thumbnail_path = self._convert_to_jpg(thumbnail_webp)

            video_info = {
                "title": title,
                "description": description,
                "upload_date": upload_date.strftime("%Y年%m月%d日"),
                "uploader": uploader,
                "video_path": str(video_path),
                "subtitle_path": subtitle_path,
                "thumbnail_path": thumbnail_path or "",
                "url": url,
            }

            logger.info(f"下载完成: {title}")
            return video_info

    def get_info(self, url: str) -> dict:
        """
        仅获取视频信息（不下载）

        Args:
            url: YouTube 视频 URL

        Returns:
            包含视频元信息的字典
        """
        logger.info(f"获取视频信息: {url}")

        ydl_opts = self._build_opts()
        ydl_opts["skip_download"] = True
        ydl_opts["writethumbnail"] = False

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            title = info.get("title", "unknown_title")
            description = info.get("description", "无描述")
            upload_date_str = info.get("upload_date", "20230101")
            upload_date = datetime.strptime(upload_date_str, '%Y%m%d')

            return {
                "title": title,
                "description": description,
                "upload_date": upload_date.strftime("%Y年%m月%d日"),
                "uploader": info.get("uploader", "未知上传者"),
                "duration": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
                "url": url,
            }


# 全局单例
youtube_svc = YouTubeService()
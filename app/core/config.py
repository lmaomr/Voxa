"""
应用配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # 应用基础配置
    APP_NAME: str = "Voxa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./voxa.db"

    # 安全配置
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 模型路径配置
    TTS_MODEL_PATH: str = "./models/VoxCPM2"
    ASR_MODEL_PATH: str = "./models/Whisper"
    UVR5_WEIGHTS_PATH: str = "./models/uvr5"

    # ASR (faster-whisper) 配置
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_MODEL_PATH: str = "./models/faster-whisper-large-v3"
    # HuggingFace 镜像（国内加速），空则直连
    HF_ENDPOINT: str = "https://hf-mirror.com"

    # 输出路径配置
    OUTPUT_DIR: str = "data/out"
    DOWNLOAD_DIR: str = "data/downloads"
    TTS_OUTPUT_DIR: str = "data/out/tts"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

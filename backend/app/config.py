"""应用配置：所有密钥与运行参数只从环境变量读取。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """集中式配置。生产环境缺少 JWT_SECRET 时服务拒绝启动。"""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Moodwave"
    app_env: str = "development"
    debug: bool = False
    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_base_url: str = "http://localhost:8000"
    cookie_secure: bool = False
    trust_proxy: bool = False
    force_https: bool = False

    jwt_secret: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'moodwave.db').as_posix()}"
    media_root: str = str(BACKEND_DIR / "media")
    max_image_mb: int = 5
    max_video_mb: int = 50

    seed_admin_email: str = "admin@moodwave.app"
    seed_admin_password: str = "Admin@12345"
    seed_user_email: str = "demo@moodwave.app"
    seed_user_password: str = "Demo@12345"
    auto_seed: bool = True

    registration_require_invite: bool = False
    registration_require_approval: bool = False

    redis_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Moodwave <no-reply@moodwave.app>"
    smtp_tls: bool = True
    dev_mailbox: bool = True

    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    oauth_redirect_base: str = "http://localhost:8000"

    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""
    presign_expire_seconds: int = 600

    enable_online_music: bool = True
    jamendo_client_id: str = ""

    sentry_dsn: str = ""
    alert_webhook_url: str = ""
    push_webhook_url: str = ""
    sms_webhook_url: str = ""
    log_level: str = "INFO"
    expose_dev_reset_link: bool = True

    # 派生路径
    model_path: Path = Field(default=BACKEND_DIR / "data" / "emotion-ferplus-8.onnx")
    upload_dir: Path = Field(default=BACKEND_DIR / "media" / "uploads")
    avatar_dir: Path = Field(default=BACKEND_DIR / "media" / "avatars")
    thumb_dir: Path = Field(default=BACKEND_DIR / "media" / "thumbs")
    demo_dir: Path = Field(default=BACKEND_DIR / "media" / "demo")
    audio_dir: Path = Field(default=BACKEND_DIR / "media" / "audio")
    banner_dir: Path = Field(default=BACKEND_DIR / "media" / "banners")
    logs_dir: Path = Field(default=BACKEND_DIR / "logs")
    frontend_dist: Path = Field(default=ROOT_DIR / "dist")

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if value and len(value) < 32:
            raise ValueError("JWT_SECRET 长度至少 32 字符")
        return value

    @model_validator(mode="after")
    def normalize_runtime_paths(self):
        """把相对路径统一锚定到项目根目录，保证从根目录或 backend 启动一致。"""
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url[len("sqlite:///") :]
            db_path = Path(raw)
            if not db_path.is_absolute():
                db_path = (ROOT_DIR / db_path).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite:///{db_path.as_posix()}"
        media = Path(self.media_root)
        if not media.is_absolute():
            media = (ROOT_DIR / media).resolve()
        self.media_root = str(media)
        self.upload_dir = media / "uploads"
        self.avatar_dir = media / "avatars"
        self.thumb_dir = media / "thumbs"
        self.demo_dir = media / "demo"
        self.audio_dir = media / "audio"
        self.banner_dir = media / "banners"
        logs = Path(self.logs_dir)
        if not logs.is_absolute():
            logs = (ROOT_DIR / logs).resolve()
        self.logs_dir = logs
        dist = Path(self.frontend_dist)
        if not dist.is_absolute():
            dist = (ROOT_DIR / dist).resolve()
        self.frontend_dist = dist
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod", "staging"}

    def ensure_directories(self) -> None:
        for folder in (
            self.upload_dir,
            self.avatar_dir,
            self.thumb_dir,
            self.demo_dir,
            self.audio_dir,
            self.banner_dir,
            self.logs_dir,
            Path(self.media_root),
            self.model_path.parent,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> None:
        if not self.jwt_secret:
            raise RuntimeError(
                "缺少 JWT_SECRET。请复制 .env.example 为 .env，并生成至少 64 位随机密钥。"
            )
        if self.is_production and self.jwt_secret.startswith("change-me"):
            raise RuntimeError("生产环境必须替换 JWT_SECRET，禁止使用示例值。")
        if self.is_production and self.cookie_secure is False:
            # 允许显式关闭，但给出响亮提示；不泄露任何密钥。
            import logging

            logging.getLogger("moodwave").warning(
                "生产环境 COOKIE_SECURE=false：请通过 HTTPS 部署并开启 Secure Cookie"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()

"""
AegisAI Application Configuration.

Uses Pydantic v2 BaseSettings for strict, typed environment variable loading.
All settings are validated at startup — missing required vars raise immediately.
"""


from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Production Application Configuration using Pydantic v2 BaseSettings.
    Loads and validates environment variables from .env file.
    All config is immutable after startup — treat as read-only.
    """

    # ----------------------------------------------------------------
    # Application Metadata
    # ----------------------------------------------------------------
    PROJECT_NAME: str = "AegisAI - AI-Powered Disaster Response & Digital Twin Platform"
    VERSION: str = "1.0.0"
    API_V1: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ----------------------------------------------------------------
    # Security & Authentication
    # ----------------------------------------------------------------
    SECRET_KEY: str = Field(
        ...,  # H6 FIX: No default — must be set via SECRET_KEY env var.
        min_length=32,
        description="HMAC signing key for JWT tokens. Min 32 chars. Set via env var only.",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ----------------------------------------------------------------
    # PostgreSQL Database
    # ----------------------------------------------------------------
    POSTGRES_SERVER: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="aegisai_db")
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")

    # Connection pool settings — tuned for production load
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800  # Recycle connections every 30 min
    DATABASE_POOL_PRE_PING: bool = True  # Validate connections before use

    # ----------------------------------------------------------------
    # Redis — Cache & Pub/Sub
    # ----------------------------------------------------------------
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_TTL_SECONDS: int = 300  # Default cache TTL: 5 minutes

    # ----------------------------------------------------------------
    # RabbitMQ — Async Event Bus
    # ----------------------------------------------------------------
    RABBITMQ_HOST: str = Field(default="localhost")
    RABBITMQ_PORT: int = Field(default=5672)
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_VHOST: str = Field(default="/")
    RABBITMQ_EXCHANGE: str = Field(default="aegisai.events")

    # ----------------------------------------------------------------
    # Ollama AI Engine
    # ----------------------------------------------------------------
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.2:3b")
    OLLAMA_TIMEOUT_SECONDS: int = 60
    OLLAMA_MAX_RETRIES: int = 2

    # ----------------------------------------------------------------
    # OSRM Routing Engine
    # ----------------------------------------------------------------
    OSRM_BASE_URL: str = Field(default="https://router.project-osrm.org")
    OSRM_TIMEOUT_SECONDS: float = 5.0

    # ----------------------------------------------------------------
    # Simulation Engine
    # ----------------------------------------------------------------
    SIMULATION_TICK_INTERVAL_SECONDS: int = 10
    SIMULATION_AUTO_START: bool = False  # Disabled by default in production
    SIMULATION_MAX_EVENT_LOG_SIZE: int = 1000

    # ----------------------------------------------------------------
    # CORS Configuration
    # ----------------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ----------------------------------------------------------------
    # Rate Limiting
    # ----------------------------------------------------------------
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "20/minute"
    RATE_LIMIT_AI: str = "20/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)  # type: ignore[arg-type]

    @property
    def DATABASE_URL(self) -> str:
        """Constructs the synchronous PostgreSQL connection URL."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Constructs the async-compatible PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        """Constructs the Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def RABBITMQ_URL(self) -> str:
        """Constructs the RabbitMQ AMQP connection URL."""
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}{self.RABBITMQ_VHOST}"
        )


settings = AppSettings()

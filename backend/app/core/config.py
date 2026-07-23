from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "极同学"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    STATIC_DIR: str = "static"

    DEEPSEEK_API_KEY: str = ""

    STORE_THINKING_IN_CONTEXT: bool = True

    MCP_SERVERS_CONFIG: str = ""

    DIFY_WORKFLOWS_CONFIG: str = ""

    SANDBOX_IMAGE: str = "ghcr.io/agent-infra/sandbox:latest"
    SANDBOX_API_KEY: str = ""
    SANDBOX_HOST_PORT_RANGE: str = "18080-18090"

    AUTH_TOKEN: str = ""


settings = Settings()

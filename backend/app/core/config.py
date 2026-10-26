from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    access_minutes: int = 15
    refresh_days: int = 7
    mfa_required: bool = False
    cors_origin: str = "http://localhost:5173"
    use_celery: bool = False  # True: pre-check runs on the Celery worker; False: inline (default for local/dev/tests)
    storage: str = "local"
    storage_dir: str = "./storage"
    file_encryption_key: str = ""
    max_upload_mb: int = 20
    trust_root_path: str = "../data/synthetic/pki/ca.pem"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio12345"
    mock_issuers_url: str = "http://mock-issuers:9000"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    feature_ocr: bool = False
    feature_layoutlm: bool = False
    feature_yolo: bool = False
    feature_face: bool = False
    feature_dtd: bool = False
    feature_llm: bool = False
    feature_rag: bool = False
    feature_real_geo: bool = False


settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Evolution API
    evolution_api_url: str
    evolution_api_key: str
    evolution_instance_name: str
    evolution_webhook_secret: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_storage_bucket: str = "workout-photos"

    # Google Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # App
    group_jid: str
    oberdan_phone: str
    timezone: str = "America/Sao_Paulo"
    debug: bool = False
    silent_mode: bool = False
    weekly_report_enabled: bool = True
    monthly_report_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()

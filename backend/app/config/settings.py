from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    chroma_persist_dir: str = "./data/chroma"

    class Config:
        env_file = ".env"


settings = Settings()

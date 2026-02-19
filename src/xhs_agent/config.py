from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    siliconflow_api_key: str
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    text_model: str = "Qwen/Qwen3-VL-32B-Instruct"

    image_api_key: str
    image_api_base_url: str
    image_model: str = "nano-banana"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


# 懒加载代理：首次访问时才实例化
class _SettingsProxy:
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()

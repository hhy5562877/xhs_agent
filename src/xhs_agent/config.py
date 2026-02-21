from .db import get_config

_DEFAULTS = {
    "siliconflow_api_key": "请在系统配置中填写",
    "siliconflow_base_url": "https://api.siliconflow.cn/v1",
    "text_model": "Qwen/Qwen3-VL-32B-Instruct",
    "vision_model": "zai-org/GLM-4.6V",
    "image_api_key": "请在系统配置中填写",
    "image_api_base_url": "请在系统配置中填写",
    "image_model": "doubao-seedream-4-5-251128",
    "wxpusher_app_token": "",
    "wxpusher_uids": "",
    "cos_secret_id": "",
    "cos_secret_key": "",
    "cos_region": "ap-guangzhou",
    "cos_bucket": "",
    "cos_path_prefix": "ref_images",
}


async def get_setting(key: str) -> str:
    return await get_config(key, _DEFAULTS.get(key, ""))

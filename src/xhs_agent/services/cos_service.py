import asyncio
import logging

from qcloud_cos import CosConfig, CosS3Client

from ..config import get_setting

logger = logging.getLogger("xhs_agent")


async def _get_client() -> tuple[CosS3Client, str, str]:
    secret_id = await get_setting("cos_secret_id")
    secret_key = await get_setting("cos_secret_key")
    region = await get_setting("cos_region")
    bucket = await get_setting("cos_bucket")

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config), bucket, region


async def upload_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    client, bucket, region = await _get_client()

    await asyncio.to_thread(
        client.put_object,
        Bucket=bucket,
        Body=data,
        Key=key,
        ContentType=content_type,
    )

    url = f"https://{bucket}.cos.{region}.myqcloud.com/{key}"
    logger.info(f"[COS] 上传成功: {url}")
    return url


async def delete_object(key: str) -> None:
    client, bucket, _ = await _get_client()

    await asyncio.to_thread(
        client.delete_object,
        Bucket=bucket,
        Key=key,
    )
    logger.info(f"[COS] 删除成功: {key}")

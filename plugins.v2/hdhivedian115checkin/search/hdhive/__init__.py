"""HDHive 签到客户端。"""
from .open import HDHiveOpenAPIClient, HDHiveOpenAPIError
from .web import HDHiveClient, HDHiveWebError

__all__ = ["HDHiveClient", "HDHiveWebError", "HDHiveOpenAPIClient", "HDHiveOpenAPIError"]


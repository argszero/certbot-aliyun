"""阿里云 DNS 辅助工具，用于自动添加/删除 DNS TXT 记录."""

import json
import logging
import time
from typing import Optional

from alibabacloud_alidns20150109.client import Client as AlidnsClient
from alibabacloud_alidns20150109 import models as alidns_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models

logger = logging.getLogger(__name__)


class AlidnsHelper:
    """阿里云 DNS 操作助手."""

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        region_id: str = "cn-hangzhou",
    ):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region_id = region_id
        self._client: Optional[AlidnsClient] = None

    @property
    def client(self) -> AlidnsClient:
        """获取阿里云 DNS 客户端."""
        if self._client is None:
            config = openapi_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                region_id=self.region_id,
            )
            self._client = AlidnsClient(config)
        return self._client

    def add_txt_record(self, domain: str, subdomain: str, value: str) -> Optional[str]:
        """添加 TXT 记录.

        Args:
            domain: 主域名，如 "example.com"
            subdomain: 子域名，如 "_acme-challenge" 或 "_acme-challenge.www"
            value: TXT 记录值

        Returns:
            记录ID，如果添加失败则返回 None
        """
        try:
            logger.info(f"添加 TXT 记录: {subdomain}.{domain} -> {value}")

            request = alidns_models.AddDomainRecordRequest(
                domain_name=domain,
                rr=subdomain,
                type="TXT",
                value=value,
                ttl=600,  # 10分钟
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.add_domain_record_with_options(request, runtime)

            if response.body.record_id:
                record_id = response.body.record_id
                logger.info(f"TXT 记录添加成功，记录ID: {record_id}")
                return record_id
            else:
                logger.error("添加 TXT 记录失败，未返回记录ID")
                return None

        except Exception as e:
            logger.error(f"添加 TXT 记录失败: {e}")
            return None

    def delete_txt_record(self, record_id: str) -> bool:
        """删除 TXT 记录.

        Args:
            record_id: 记录ID

        Returns:
            是否删除成功
        """
        try:
            logger.info(f"删除 TXT 记录，记录ID: {record_id}")

            request = alidns_models.DeleteDomainRecordRequest(
                record_id=record_id,
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.delete_domain_record_with_options(request, runtime)

            if response.body.request_id:
                logger.info(f"TXT 记录删除成功: {record_id}")
                return True
            else:
                logger.warning(f"删除 TXT 记录可能失败: {record_id}")
                return False

        except Exception as e:
            logger.error(f"删除 TXT 记录失败: {e}")
            return False

    def find_txt_record(self, domain: str, subdomain: str, value: str) -> Optional[str]:
        """查找 TXT 记录.

        Args:
            domain: 主域名
            subdomain: 子域名
            value: TXT 记录值

        Returns:
            记录ID，如果未找到则返回 None
        """
        try:
            logger.info(f"查找 TXT 记录: {subdomain}.{domain} -> {value}")

            request = alidns_models.DescribeDomainRecordsRequest(
                domain_name=domain,
                rr_key_word=subdomain,
                type="TXT",
                value_key_word=value,
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.describe_domain_records_with_options(request, runtime)

            if response.body.domain_records and response.body.domain_records.record:
                for record in response.body.domain_records.record:
                    if (record.rr == subdomain and record.type == "TXT" and
                        record.value == value):
                        logger.info(f"找到 TXT 记录，记录ID: {record.record_id}")
                        return record.record_id

            logger.info(f"未找到匹配的 TXT 记录")
            return None

        except Exception as e:
            logger.error(f"查找 TXT 记录失败: {e}")
            return None

    def wait_for_dns_propagation(
        self, domain: str, subdomain: str, value: str, timeout: int = 300
    ) -> bool:
        """等待 DNS 记录传播.

        Args:
            domain: 主域名
            subdomain: 子域名
            value: TXT 记录值
            timeout: 超时时间（秒）

        Returns:
            是否传播成功
        """
        logger.info(f"等待 DNS 记录传播: {subdomain}.{domain} -> {value}")

        start_time = time.time()
        check_interval = 10  # 每10秒检查一次

        while time.time() - start_time < timeout:
            try:
                # 尝试查找记录
                record_id = self.find_txt_record(domain, subdomain, value)
                if record_id:
                    logger.info(f"DNS 记录已传播: {subdomain}.{domain}")
                    return True

                # 等待一段时间再检查
                elapsed = int(time.time() - start_time)
                logger.info(f"DNS 传播等待中... ({elapsed}/{timeout}秒)")
                time.sleep(check_interval)

            except Exception as e:
                logger.warning(f"DNS 传播检查失败: {e}")
                time.sleep(check_interval)

        logger.warning(f"DNS 记录传播超时: {subdomain}.{domain}")
        return False


def extract_domain_parts(full_domain: str) -> tuple[str, str]:
    """从完整域名中提取主域名和子域名部分.

    Args:
        full_domain: 完整域名，如 "_acme-challenge.www.example.com"

    Returns:
        (主域名, 子域名)

    Example:
        extract_domain_parts("_acme-challenge.www.example.com")
        -> ("example.com", "_acme-challenge.www")
    """
    # 移除可能的通配符
    if full_domain.startswith("*."):
        full_domain = full_domain[2:]

    # 分割域名部分
    parts = full_domain.split(".")

    if len(parts) >= 2:
        # 主域名是最后两部分
        main_domain = ".".join(parts[-2:])
        # 子域名是前面的部分
        subdomain = ".".join(parts[:-2]) if len(parts) > 2 else "@"
    else:
        main_domain = full_domain
        subdomain = "@"

    return main_domain, subdomain


# 全局助手实例
_alidns_helper: Optional[AlidnsHelper] = None


def get_alidns_helper() -> AlidnsHelper:
    """获取阿里云 DNS 助手实例."""
    global _alidns_helper
    if _alidns_helper is None:
        from .config import Config
        _alidns_helper = AlidnsHelper(
            access_key_id=Config.ALIBABA_CLOUD_ACCESS_KEY_ID,
            access_key_secret=Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            region_id=Config.ALIBABA_CLOUD_REGION_ID,
        )
    return _alidns_helper
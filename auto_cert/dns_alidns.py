"""阿里云 DNS 验证插件 for Certbot."""

import json
import logging
import time
from typing import Any, Optional, Callable, List

from alibabacloud_alidns20150109.client import Client as AlidnsClient
from alibabacloud_alidns20150109 import models as alidns_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from certbot import errors
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)


class Authenticator(dns_common.DNSAuthenticator):
    """阿里云 DNS 验证插件."""

    description = "通过阿里云 DNS API 进行 DNS-01 挑战验证"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.credentials: Optional[dns_common.CredentialsConfiguration] = None

    @classmethod
    def add_parser_arguments(
        cls, add: Callable[..., None], default_propagation_seconds: int = 30
    ) -> None:
        super().add_parser_arguments(add, default_propagation_seconds)
        # 不再需要credentials参数，直接从环境变量读取

    def more_info(self) -> str:
        return (
            "该插件通过阿里云 DNS API 完成 DNS-01 挑战验证。"
            "需要配置阿里云 AccessKey 和域名信息。"
        )

    def _setup_credentials(self) -> None:
        # 直接从环境变量获取凭证，不需要凭证文件
        import os
        from certbot import errors

        self.access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        self.access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        self.region_id = os.getenv("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")

        if not self.access_key_id or not self.access_key_secret:
            raise errors.PluginError("阿里云凭证未配置，请设置 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET 环境变量")

        # 获取域名
        from .config import Config
        if Config.CERT_DOMAINS:
            # 使用第一个域名的根域名
            domain = Config.CERT_DOMAINS[0].strip()
            if domain.startswith("*."):
                self.domain = domain[2:]
            else:
                self.domain = domain
        else:
            raise errors.PluginError("未配置证书域名")

    def _perform(self, domain: str, validation_name: str, validation: str) -> None:
        logger.info(f"执行 DNS-01 挑战: domain={domain}, validation_name={validation_name}, validation={validation[:20]}...")
        self._get_alidns_client().add_txt_record(
            domain=domain,
            validation_name=validation_name,
            validation=validation,
        )

    def _cleanup(self, domain: str, validation_name: str, validation: str) -> None:
        self._get_alidns_client().del_txt_record(
            domain=domain,
            validation_name=validation_name,
            validation=validation,
        )

    def _get_alidns_client(self) -> "AlidnsHandler":
        # 确保凭证已设置
        if not hasattr(self, 'access_key_id') or not self.access_key_id:
            self._setup_credentials()

        return AlidnsHandler(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            region_id=self.region_id,
            domain=self.domain,
        )


class AlidnsHandler:
    """阿里云 DNS 操作处理器."""

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        region_id: str,
        domain: str,
    ) -> None:
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region_id = region_id
        self.domain = domain
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

    def _get_existing_txt_records(self, subdomain: str) -> List[alidns_models.DescribeDomainRecordsResponseBodyDomainRecordsRecord]:
        """获取所有已存在的 TXT 记录对象."""
        try:
            request = alidns_models.DescribeDomainRecordsRequest(
                domain_name=self.domain,
                rrkey_word=subdomain,
                type="TXT",
            )
            runtime = util_models.RuntimeOptions()
            response = self.client.describe_domain_records_with_options(request, runtime)

            if response.body.domain_records and response.body.domain_records.record:
                return response.body.domain_records.record
            return []
        except Exception as e:
            logger.warning(f"获取 TXT 记录失败: {e}")
            return []

    def _update_txt_record(self, record_id: str, existing_value: str, new_value: str) -> None:
        """更新 TXT 记录，添加新值."""
        try:
            # TXT 记录可以包含多个字符串，用空格分隔
            # 但 Let's Encrypt 可能期望单独的值，所以我们需要决定如何处理
            # 这里我们创建新记录并删除旧记录，因为更新可能不支持添加值

            # 首先删除旧记录
            delete_request = alidns_models.DeleteDomainRecordRequest(
                record_id=record_id,
            )
            runtime = util_models.RuntimeOptions()
            self.client.delete_domain_record_with_options(delete_request, runtime)

            # 创建新记录包含所有值
            # 注意：这里简化处理，实际可能需要更复杂的逻辑来处理多个值
            updated_value = f"{existing_value} {new_value}"

            # 提取子域名（需要从现有记录获取，这里简化）
            # 实际上我们需要保存子域名信息，这里先创建简单实现
            logger.warning(f"更新 TXT 记录功能简化实现，可能需要完善")

        except Exception as e:
            logger.error(f"更新 TXT 记录失败: {e}")
            raise errors.PluginError(f"更新 TXT 记录失败: {e}")

    def add_txt_record(
        self, domain: str, validation_name: str, validation: str
    ) -> None:
        """添加 TXT 记录."""
        try:
            # 提取子域名部分
            # 正确的方法：移除域名部分
            if validation_name.endswith("." + self.domain):
                subdomain = validation_name[:-(len(self.domain) + 1)]  # +1 for the dot
            elif validation_name == self.domain:
                subdomain = "@"
            else:
                subdomain = validation_name.rstrip(".")

            logger.info(f"添加 TXT 记录: {subdomain}.{self.domain} -> {validation}")

            # 直接创建新记录（DNS允许同一主机名有多个TXT记录）
            request = alidns_models.AddDomainRecordRequest(
                domain_name=self.domain,
                rr=subdomain,
                type="TXT",
                value=validation,
                ttl=600,  # 10分钟
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.add_domain_record_with_options(request, runtime)

            if response.body.record_id:
                logger.info(f"TXT 记录添加成功，记录ID: {response.body.record_id}")
                # 保存记录ID以便清理
                self._save_record_id(validation_name, response.body.record_id)
            else:
                raise errors.PluginError("添加 TXT 记录失败")

            # 不在这里等待 DNS 传播，Certbot 会根据 propagation-seconds 参数处理等待

        except Exception as e:
            logger.error(f"添加 TXT 记录失败: {e}")
            raise errors.PluginError(f"添加 TXT 记录失败: {e}")

    def del_txt_record(
        self, domain: str, validation_name: str, validation: str
    ) -> None:
        """删除 TXT 记录."""
        try:
            # 首先尝试从文件获取记录ID
            record_id = self._get_record_id(validation_name)

            # 如果文件不存在，尝试通过API查找记录
            if not record_id:
                # 提取子域名部分
                # 正确的方法：移除域名部分
                if validation_name.endswith("." + self.domain):
                    subdomain = validation_name[:-(len(self.domain) + 1)]  # +1 for the dot
                elif validation_name == self.domain:
                    subdomain = "@"
                else:
                    subdomain = validation_name.rstrip(".")

                # 查找所有 _acme-challenge TXT 记录
                existing_records = self._get_existing_txt_records(subdomain)
                if not existing_records:
                    logger.warning(f"未找到 TXT 记录: {validation_name}")
                    return

                # 删除所有找到的记录（清理时删除所有 _acme-challenge 记录）
                logger.info(f"找到 {len(existing_records)} 个 _acme-challenge 记录，全部删除")
                for record in existing_records:
                    self._delete_single_txt_record(record.record_id, validation_name)
                return

            # 删除单个记录
            self._delete_single_txt_record(record_id, validation_name)

        except Exception as e:
            logger.error(f"删除 TXT 记录失败: {e}")
            # 不抛出异常，避免影响证书申请流程

    def _delete_single_txt_record(self, record_id: str, validation_name: str) -> None:
        """删除单个 TXT 记录."""
        try:
            logger.info(f"删除 TXT 记录，记录ID: {record_id}")

            request = alidns_models.DeleteDomainRecordRequest(
                record_id=record_id,
            )

            runtime = util_models.RuntimeOptions()
            response = self.client.delete_domain_record_with_options(request, runtime)

            if response.body.request_id:
                logger.info(f"TXT 记录删除成功: {record_id}")
                # 尝试删除对应的文件（如果存在）
                self._remove_record_id(validation_name)
            else:
                logger.warning(f"删除 TXT 记录可能失败: {record_id}")

        except Exception as e:
            logger.error(f"删除单个 TXT 记录失败: {e}")
            # 不抛出异常，避免影响证书申请流程


    def _save_record_id(self, validation_name: str, record_id: str) -> None:
        """保存记录ID到临时文件."""
        try:
            import os
            from pathlib import Path

            # 使用 validation_name 和 record_id 的哈希作为文件名，避免冲突
            import hashlib
            file_hash = hashlib.md5(f"{validation_name}:{record_id}".encode()).hexdigest()[:8]
            record_file = Path("/tmp") / f"alidns_record_{file_hash}.txt"
            record_file.write_text(f"{validation_name}:{record_id}")
            logger.debug(f"保存记录ID到文件: {record_file}")

        except Exception as e:
            logger.warning(f"保存记录ID失败: {e}")

    def _get_record_id(self, validation_name: str) -> Optional[str]:
        """从临时文件获取记录ID."""
        try:
            import os
            from pathlib import Path

            # 查找所有匹配 validation_name 的文件
            tmp_dir = Path("/tmp")
            for record_file in tmp_dir.glob("alidns_record_*.txt"):
                try:
                    content = record_file.read_text().strip()
                    if content.startswith(f"{validation_name}:"):
                        # 返回 record_id 部分
                        return content.split(":", 1)[1]
                except Exception:
                    continue
            return None

        except Exception as e:
            logger.warning(f"获取记录ID失败: {e}")
            return None

    def _remove_record_id(self, validation_name: str) -> None:
        """删除临时记录ID文件."""
        try:
            import os
            from pathlib import Path

            # 删除所有匹配 validation_name 的文件
            tmp_dir = Path("/tmp")
            for record_file in tmp_dir.glob("alidns_record_*.txt"):
                try:
                    content = record_file.read_text().strip()
                    if content.startswith(f"{validation_name}:"):
                        record_file.unlink()
                        logger.debug(f"删除记录ID文件: {record_file}")
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"删除记录ID文件失败: {e}")
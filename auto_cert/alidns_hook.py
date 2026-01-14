#!/usr/bin/env python3
"""
阿里云 DNS hook脚本，用于certbot的manual-auth-hook和manual-cleanup-hook。
通过环境变量获取阿里云凭证，自动添加/删除DNS TXT记录。
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_alidns_client():
    """获取阿里云DNS客户端"""
    from alibabacloud_alidns20150109.client import Client as AlidnsClient
    from alibabacloud_alidns20150109 import models as alidns_models
    from alibabacloud_tea_openapi import models as openapi_models
    from alibabacloud_tea_util import models as util_models

    # 从环境变量获取凭证
    access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    region_id = os.getenv("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")

    if not access_key_id or not access_key_secret:
        logger.error("阿里云凭证未配置，请设置 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET 环境变量")
        sys.exit(1)

    # 创建客户端
    config = openapi_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )
    return AlidnsClient(config)




def add_txt_record(domain: str, validation_name: str, validation: str):
    """添加TXT记录"""
    try:
        client = get_alidns_client()

        # 从CERTBOT_DOMAIN中提取根域名
        # 如果domain以*.开头，去掉*.前缀
        if domain.startswith("*."):
            root_domain = domain[2:]
        else:
            # 尝试提取根域名：去掉第一个点之前的部分
            parts = domain.split(".")
            if len(parts) >= 2:
                # 取最后两部分作为根域名（例如：test.example.com -> example.com）
                root_domain = ".".join(parts[-2:])
            else:
                # 如果只有一个部分，使用它作为根域名
                root_domain = domain

        logger.info(f"处理域名: {domain}, 根域名: {root_domain}")

        # 处理验证名称中的通配符
        # 如果validation_name包含*.，去掉*.部分
        if ".*." in validation_name:
            # 例如: _acme-challenge.*.example.com -> _acme-challenge.example.com
            validation_name = validation_name.replace(".*.", ".")
            logger.info(f"处理通配符验证名称，更新为: {validation_name}")

        # 提取子域名部分
        if validation_name.endswith("." + root_domain):
            subdomain = validation_name[:-(len(root_domain) + 1)]  # +1 for the dot
        elif validation_name == root_domain:
            subdomain = "@"
        else:
            subdomain = validation_name.rstrip(".")

        logger.info(f"添加 TXT 记录: {subdomain}.{root_domain} -> {validation}")

        from alibabacloud_alidns20150109 import models as alidns_models
        from alibabacloud_tea_util import models as util_models

        request = alidns_models.AddDomainRecordRequest(
            domain_name=root_domain,
            rr=subdomain,
            type="TXT",
            value=validation,
            ttl=600,  # 10分钟
        )

        runtime = util_models.RuntimeOptions()
        response = client.add_domain_record_with_options(request, runtime)

        if response.body.record_id:
            logger.info(f"TXT 记录添加成功，记录ID: {response.body.record_id}")
            # 保存记录ID以便清理
            save_record_id(validation_name, response.body.record_id)
        else:
            logger.error("添加 TXT 记录失败")
            sys.exit(1)

    except Exception as e:
        logger.error(f"添加 TXT 记录失败: {e}")
        sys.exit(1)


def delete_txt_record(domain: str, validation_name: str, validation: str):
    """删除TXT记录"""
    try:
        client = get_alidns_client()

        # 从CERTBOT_DOMAIN中提取根域名
        # 如果domain以*.开头，去掉*.前缀
        if domain.startswith("*."):
            root_domain = domain[2:]
        else:
            # 尝试提取根域名：去掉第一个点之前的部分
            parts = domain.split(".")
            if len(parts) >= 2:
                # 取最后两部分作为根域名（例如：test.example.com -> example.com）
                root_domain = ".".join(parts[-2:])
            else:
                # 如果只有一个部分，使用它作为根域名
                root_domain = domain

        logger.info(f"处理域名: {domain}, 根域名: {root_domain}")

        # 处理验证名称中的通配符（与add_txt_record保持一致）
        # 如果validation_name包含*.，去掉*.部分
        if ".*." in validation_name:
            # 例如: _acme-challenge.*.example.com -> _acme-challenge.example.com
            validation_name = validation_name.replace(".*.", ".")
            logger.info(f"处理通配符验证名称，更新为: {validation_name}")

        # 首先尝试从文件获取记录ID
        logger.info(f"尝试获取记录ID，验证名称: {validation_name}")
        record_id = get_record_id(validation_name)

        if record_id:
            logger.info(f"找到记录ID: {record_id}")
            # 删除指定记录
            delete_single_record(client, record_id, validation_name)
        else:
            logger.warning(f"未找到记录ID文件，尝试通过API查找并删除")
            # 如果文件不存在，尝试通过API查找并删除
            delete_by_api(client, root_domain, validation_name)

    except Exception as e:
        logger.error(f"删除 TXT 记录失败: {e}")
        # 不退出，避免影响证书申请流程


def delete_single_record(client, record_id: str, validation_name: str):
    """删除单个记录"""
    try:
        from alibabacloud_alidns20150109 import models as alidns_models
        from alibabacloud_tea_util import models as util_models

        logger.info(f"删除 TXT 记录，记录ID: {record_id}")

        request = alidns_models.DeleteDomainRecordRequest(
            record_id=record_id,
        )

        runtime = util_models.RuntimeOptions()
        response = client.delete_domain_record_with_options(request, runtime)

        if response.body.request_id:
            logger.info(f"TXT 记录删除成功: {record_id}")
            remove_record_id(validation_name)
        else:
            logger.warning(f"删除 TXT 记录可能失败: {record_id}")

    except Exception as e:
        logger.error(f"删除单个 TXT 记录失败: {e}")


def delete_by_api(client, root_domain: str, validation_name: str):
    """通过API查找并删除记录"""
    try:
        from alibabacloud_alidns20150109 import models as alidns_models
        from alibabacloud_tea_util import models as util_models

        logger.info(f"delete_by_api: root_domain={root_domain}, validation_name={validation_name}")

        # 处理验证名称中的通配符（与add_txt_record保持一致）
        # 如果validation_name包含*.，去掉*.部分
        if ".*." in validation_name:
            # 例如: _acme-challenge.*.example.com -> _acme-challenge.example.com
            validation_name = validation_name.replace(".*.", ".")
            logger.info(f"处理通配符验证名称，更新为: {validation_name}")

        # 提取子域名部分
        if validation_name.endswith("." + root_domain):
            subdomain = validation_name[:-(len(root_domain) + 1)]  # +1 for the dot
        elif validation_name == root_domain:
            subdomain = "@"
        else:
            subdomain = validation_name.rstrip(".")

        # 查找所有 _acme-challenge TXT 记录
        request = alidns_models.DescribeDomainRecordsRequest(
            domain_name=root_domain,
            rrkey_word=subdomain,
            type="TXT",
        )
        runtime = util_models.RuntimeOptions()
        response = client.describe_domain_records_with_options(request, runtime)

        if (response.body.domain_records and
            response.body.domain_records.record):
            records = response.body.domain_records.record
            logger.info(f"找到 {len(records)} 个 _acme-challenge 记录，全部删除")
            for record in records:
                delete_single_record(client, record.record_id, validation_name)
        else:
            logger.warning(f"未找到 TXT 记录: {validation_name}")

    except Exception as e:
        logger.error(f"通过API查找记录失败: {e}")


def save_record_id(validation_name: str, record_id: str):
    """保存记录ID到文件"""
    try:
        logger.info(f"保存记录ID: 验证名称={validation_name}, 记录ID={record_id}")

        # 使用certbot配置目录保存记录ID，确保cleanup hook能访问
        from .config import Config

        # 创建记录目录
        record_dir = Config.CERTBOT_CONFIG_DIR / "alidns_records"
        record_dir.mkdir(parents=True, exist_ok=True)

        # 使用验证名称作为文件名（确保唯一性）
        # 替换特殊字符为下划线
        safe_name = validation_name.replace(".", "_").replace("*", "wildcard")
        record_file = record_dir / f"{safe_name}.txt"

        # 保存记录ID和验证名称
        file_content = f"{validation_name}:{record_id}"
        record_file.write_text(file_content)
        logger.info(f"记录ID已保存到: {record_file}")

    except Exception as e:
        logger.warning(f"保存记录ID失败: {e}")


def get_record_id(validation_name: str):
    """获取记录ID"""
    try:
        logger.info(f"获取记录ID: 验证名称={validation_name}")

        # 从certbot配置目录获取
        from .config import Config
        record_dir = Config.CERTBOT_CONFIG_DIR / "alidns_records"

        if record_dir.exists():
            # 查找匹配的文件
            safe_name = validation_name.replace(".", "_").replace("*", "wildcard")
            record_file = record_dir / f"{safe_name}.txt"

            if record_file.exists():
                content = record_file.read_text().strip()
                if content.startswith(f"{validation_name}:"):
                    record_id = content.split(":", 1)[1]
                    logger.info(f"找到记录ID: {record_id}")
                    return record_id
                else:
                    logger.warning(f"文件内容不匹配: {record_file}")
            else:
                logger.warning(f"记录文件不存在: {record_file}")
        else:
            logger.warning(f"记录目录不存在: {record_dir}")

        logger.warning(f"未找到记录ID: {validation_name}")
        return None
    except Exception as e:
        logger.warning(f"获取记录ID失败: {e}")
        return None


def remove_record_id(validation_name: str):
    """删除记录ID文件"""
    try:
        logger.info(f"删除记录ID文件: 验证名称={validation_name}")

        # 删除配置目录中的文件
        from .config import Config
        record_dir = Config.CERTBOT_CONFIG_DIR / "alidns_records"

        if record_dir.exists():
            safe_name = validation_name.replace(".", "_").replace("*", "wildcard")
            record_file = record_dir / f"{safe_name}.txt"

            if record_file.exists():
                record_file.unlink()
                logger.info(f"已删除记录ID文件: {record_file}")
            else:
                logger.warning(f"记录文件不存在: {record_file}")
        else:
            logger.warning(f"记录目录不存在: {record_dir}")

    except Exception as e:
        logger.warning(f"删除记录ID文件失败: {e}")


def main():
    """主函数"""
    # certbot会传递环境变量：
    # CERTBOT_DOMAIN: 当前验证的域名
    # CERTBOT_VALIDATION: 验证字符串
    # CERTBOT_TOKEN: 仅用于http-01验证
    # CERTBOT_AUTH_OUTPUT: hook脚本的输出文件（仅cleanup阶段）
    # CERTBOT_REMAINING_CHALLENGES: 剩余挑战数量

    # 记录所有相关环境变量用于调试
    logger.info("=== Hook脚本开始执行 ===")
    logger.info(f"当前工作目录: {os.getcwd()}")
    logger.info(f"Python路径: {sys.executable}")

    # 非常明显的日志，确保我们能知道hook是否被调用
    print("=== CERTBOT HOOK SCRIPT EXECUTED ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Domain: {os.getenv('CERTBOT_DOMAIN', 'NOT SET')}")
    print(f"Auth output: {os.getenv('CERTBOT_AUTH_OUTPUT', 'NOT SET')}")
    print("=====================================")

    # 记录关键环境变量
    env_vars_to_log = [
        "CERTBOT_DOMAIN", "CERTBOT_VALIDATION", "CERTBOT_AUTH_OUTPUT",
        "CERTBOT_REMAINING_CHALLENGES", "CERTBOT_TOKEN",
        "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_REGION_ID",
        "CERT_DOMAINS", "PATH"
    ]

    for env_var in env_vars_to_log:
        value = os.getenv(env_var)
        if value:
            if "KEY" in env_var or "SECRET" in env_var:
                logger.info(f"{env_var}: {'*' * 8}{value[-4:] if len(value) > 4 else '****'}")
            else:
                logger.info(f"{env_var}: {value}")
        else:
            logger.warning(f"{env_var}: 未设置")

    domain = os.getenv("CERTBOT_DOMAIN")
    validation = os.getenv("CERTBOT_VALIDATION")
    auth_output = os.getenv("CERTBOT_AUTH_OUTPUT")

    if not domain or not validation:
        logger.error("缺少必要的环境变量: CERTBOT_DOMAIN 或 CERTBOT_VALIDATION")
        sys.exit(1)

    # 构建验证名称（_acme-challenge.<domain>）
    validation_name = f"_acme-challenge.{domain}"

    logger.info(f"处理域名: {domain}, 验证名称: {validation_name}, 验证值: {validation[:20]}...")

    # 判断是auth阶段还是cleanup阶段
    # cleanup阶段会有CERTBOT_AUTH_OUTPUT环境变量
    if auth_output:
        # cleanup阶段：删除TXT记录
        logger.info("cleanup阶段：删除TXT记录")
        delete_txt_record(domain, validation_name, validation)
    else:
        # auth阶段：添加TXT记录
        logger.info("auth阶段：添加TXT记录")
        add_txt_record(domain, validation_name, validation)

        # 输出信息到文件（如果需要）
        if os.getenv("CERTBOT_AUTH_OUTPUT"):
            with open(os.getenv("CERTBOT_AUTH_OUTPUT"), "w") as f:
                f.write(f"Added TXT record for {validation_name}")

    logger.info("hook脚本执行完成")


if __name__ == "__main__":
    main()
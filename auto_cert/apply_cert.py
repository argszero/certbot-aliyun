"""Script 1: Apply for Let's Encrypt certificates."""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .alidns_helper import AlidnsHelper, extract_domain_parts

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_certbot() -> bool:
    """Run certbot to apply for certificates."""
    try:
        # Create necessary directories
        Config.CERT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        Config.CERTBOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Get certbot arguments
        args = ["certbot"] + Config.get_certbot_args()

        logger.info(f"Running certbot with args: {' '.join(args)}")
        logger.info(f"Domains: {', '.join(Config.CERT_DOMAINS)}")
        logger.info(f"Email: {Config.CERT_EMAIL}")
        logger.info(f"Staging mode: {Config.CERT_STAGING}")
        logger.info(f"Validation method: {Config.CERT_VALIDATION_METHOD}")

        # 根据验证方法选择不同的运行方式
        if Config.CERT_VALIDATION_METHOD == "manual":
            return _run_manual_validation(args)
        else:
            # dns-alidns, dns-route53, standalone 都使用标准验证
            return _run_standard_validation(args)

    except Exception as e:
        logger.error(f"Error running certbot: {e}")
        return False


def _run_manual_validation(args: list) -> bool:
    """运行手动 DNS 验证."""
    logger.info("=" * 60)
    logger.info("手动DNS验证说明:")
    logger.info("1. certbot会显示需要添加的DNS TXT记录")
    logger.info("2. 请登录阿里云DNS控制台添加这些TXT记录")
    logger.info("3. 添加后等待几分钟让DNS生效")
    logger.info("4. 按回车键继续验证")
    logger.info("=" * 60)

    logger.info("正在启动交互式certbot...")
    logger.info("请按照certbot的提示操作:")
    logger.info("1. 添加DNS TXT记录")
    logger.info("2. 等待DNS生效")
    logger.info("3. 按回车键继续")

    # 使用交互式模式运行，传递环境变量
    env = os.environ.copy()
    # 设置必要的环境变量供hook脚本使用（对于manual模式，hook可能不会被调用，但为了安全还是设置）
    env["CERT_DOMAINS"] = ",".join(Config.CERT_DOMAINS)
    env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = Config.ALIBABA_CLOUD_ACCESS_KEY_ID
    env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET
    env["ALIBABA_CLOUD_REGION_ID"] = Config.ALIBABA_CLOUD_REGION_ID

    result = subprocess.run(args, text=True, env=env)

    if result.returncode == 0:
        logger.info("手动验证完成，证书应该已申请成功")
        return True
    else:
        logger.error("Certificate application failed in manual mode")
        return False




def _run_standard_validation(args: list) -> bool:
    """运行标准验证（非手动模式）."""
    # 获取当前环境变量并传递给certbot
    env = os.environ.copy()
    # 设置必要的环境变量供hook脚本使用
    env["CERT_DOMAINS"] = ",".join(Config.CERT_DOMAINS)
    env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = Config.ALIBABA_CLOUD_ACCESS_KEY_ID
    env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET
    env["ALIBABA_CLOUD_REGION_ID"] = Config.ALIBABA_CLOUD_REGION_ID

    result = subprocess.run(args, capture_output=True, text=True, env=env)

    if result.returncode == 0:
        logger.info("Certificate application successful!")
        logger.info(result.stdout)

        # 解析输出只是为了日志记录，不再保存到JSON文件
        cert_info = parse_certbot_output(result.stdout)
        if cert_info:
            logger.info(f"Certificate application information parsed: {cert_info}")
        else:
            logger.warning("Could not parse certificate information from output")
        return True  # Still consider it successful if certbot succeeded
    else:
        logger.error(f"Certificate application failed: {result.stderr}")
        return False


def parse_certbot_output(output: str) -> dict:
    """Parse certbot output to extract certificate information."""
    cert_info = {}
    lines = output.split("\n")

    for line in lines:
        line = line.strip()
        if "Congratulations!" in line:
            # Certbot success message found
            cert_info["status"] = "success"
        elif "Your certificate and chain have been saved at:" in line or "Certificate is saved at:" in line:
            # Extract certificate path
            parts = line.split(":")
            if len(parts) > 1:
                cert_info["cert_path"] = parts[1].strip()
        elif "Your key file has been saved at:" in line or "Key is saved at:" in line:
            # Extract key file path
            parts = line.split(":")
            if len(parts) > 1:
                cert_info["key_path"] = parts[1].strip()
        elif "Your certificate will expire on" in line or "This certificate expires on" in line:
            # Extract expiration date
            parts = line.split("on")
            if len(parts) > 1:
                cert_info["expires"] = parts[1].strip()

    return cert_info


def find_certificate_files() -> dict:
    """Find certificate files in certbot config directory."""
    try:
        cert_info = {}

        live_dir = Config.CERTBOT_CONFIG_DIR / "live"
        if live_dir.exists():
            # First, try exact domain names from config
            for domain in Config.CERT_DOMAINS:
                domain_clean = domain.strip()
                # Try exact domain name first
                domain_dir = live_dir / domain_clean
                if domain_dir.exists():
                    cert_path = domain_dir / "fullchain.pem"
                    key_path = domain_dir / "privkey.pem"

                    if cert_path.exists() and key_path.exists():
                        cert_info["cert_path"] = str(cert_path)
                        cert_info["key_path"] = str(key_path)
                        cert_info["status"] = "found"
                        logger.info(f"Found certificate files for {domain}")
                        return cert_info

            # If no exact match, look for any certificate directory
            for item in live_dir.iterdir():
                if item.is_dir():
                    cert_path = item / "fullchain.pem"
                    key_path = item / "privkey.pem"

                    if cert_path.exists() and key_path.exists():
                        cert_info["cert_path"] = str(cert_path)
                        cert_info["key_path"] = str(key_path)
                        cert_info["status"] = "found"
                        logger.info(f"Found certificate files in {item.name}")
                        return cert_info

        return cert_info
    except Exception as e:
        logger.error(f"Error finding certificate files: {e}")
        return {}






def main() -> None:
    """Main function for applying certificates."""
    logger.info("Starting certificate application...")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    # Run certbot
    success = run_certbot()

    if success:
        logger.info("Certificate application completed successfully!")
        sys.exit(0)
    else:
        logger.error("Certificate application failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
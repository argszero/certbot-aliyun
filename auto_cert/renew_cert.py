"""Script 2: Renew Let's Encrypt certificates."""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_certificate_expiry_from_file(cert_path: str) -> datetime:
    """Get certificate expiry date directly from certificate file using openssl."""
    try:
        # Use openssl to read certificate expiry
        result = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-noout", "-enddate"],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output: "notAfter=Jan 13 12:00:00 2025 GMT"
        enddate_str = result.stdout.strip()
        if "notAfter=" in enddate_str:
            date_str = enddate_str.replace("notAfter=", "")
            # Parse date: "Jan 13 12:00:00 2025 GMT"
            return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
    except Exception as e:
        logger.error(f"Error reading certificate expiry from {cert_path}: {e}")

    return None


def find_certificate_file() -> str:
    """Find certificate file in certbot config directory."""
    try:
        live_dir = Config.CERTBOT_CONFIG_DIR / "live"
        if live_dir.exists():
            # First, try exact domain names from config
            for domain in Config.CERT_DOMAINS:
                domain_clean = domain.strip()
                domain_dir = live_dir / domain_clean
                cert_path = domain_dir / "fullchain.pem"
                if cert_path.exists():
                    return str(cert_path)

            # If no exact match, look for any certificate directory
            for item in live_dir.iterdir():
                if item.is_dir():
                    cert_path = item / "fullchain.pem"
                    if cert_path.exists():
                        return str(cert_path)
    except Exception as e:
        logger.error(f"Error finding certificate file: {e}")

    return None


def check_certificate_expiry() -> bool:
    """Check if certificate needs renewal by reading directly from certificate file."""
    try:
        # Find certificate file
        cert_path = find_certificate_file()
        if not cert_path:
            logger.warning("No certificate file found. Certificate may not exist.")
            return True  # Need to apply for new certificate

        # Get expiry date directly from certificate file
        expiry_date = get_certificate_expiry_from_file(cert_path)
        if not expiry_date:
            logger.warning("Could not read expiration date from certificate file. Assuming renewal needed.")
            return True

        # Check if certificate expires within 30 days
        renewal_threshold = datetime.now() + timedelta(days=30)

        if expiry_date < renewal_threshold:
            logger.info(f"Certificate expires on {expiry_date.strftime('%Y-%m-%d')}. Renewal needed.")
            return True
        else:
            days_remaining = (expiry_date - datetime.now()).days
            logger.info(f"Certificate expires on {expiry_date.strftime('%Y-%m-%d')} ({days_remaining} days remaining). No renewal needed yet.")
            return False

    except Exception as e:
        logger.error(f"Error checking certificate expiry: {e}")
        return True  # Assume renewal needed on error


def renew_certificate() -> bool:
    """Renew certificate using certbot."""
    try:
        # Create necessary directories
        Config.CERT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        Config.CERTBOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # For manual validation, we need to use certonly command with --force-renewal
        # instead of renew command which doesn't support manual validation
        args = ["certbot"] + Config.get_certbot_args()
        args.append("--force-renewal")  # Force renewal even if not expired

        logger.info(f"Running certbot certonly with force renewal: {' '.join(args)}")
        logger.info(f"Domains: {', '.join(Config.CERT_DOMAINS)}")

        # Special handling for manual validation
        if Config.CERT_VALIDATION_METHOD == "manual":
            logger.info("=" * 60)
            logger.info("手动DNS验证说明:")
            logger.info("1. certbot会显示需要添加的DNS TXT记录")
            logger.info("2. 请登录阿里云DNS控制台添加这些TXT记录")
            logger.info("3. 添加后等待几分钟让DNS生效")
            logger.info("4. 按回车键继续验证")
            logger.info("=" * 60)

            # 对于手动验证，我们需要交互式运行certbot
            env = os.environ.copy()
            # 设置必要的环境变量供hook脚本使用
            env["CERT_DOMAINS"] = ",".join(Config.CERT_DOMAINS)
            env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = Config.ALIBABA_CLOUD_ACCESS_KEY_ID
            env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET
            env["ALIBABA_CLOUD_REGION_ID"] = Config.ALIBABA_CLOUD_REGION_ID

            result = subprocess.run(args, text=True, env=env)
        else:
            # 非手动模式使用非交互式运行
            env = os.environ.copy()
            # 设置必要的环境变量供hook脚本使用
            env["CERT_DOMAINS"] = ",".join(Config.CERT_DOMAINS)
            env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = Config.ALIBABA_CLOUD_ACCESS_KEY_ID
            env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET
            env["ALIBABA_CLOUD_REGION_ID"] = Config.ALIBABA_CLOUD_REGION_ID

            result = subprocess.run(args, capture_output=True, text=True, env=env)

        if result.returncode == 0:
            logger.info("Certificate renewal successful!")

            # 对于手动模式，我们无法捕获输出，但可以尝试读取证书文件
            if Config.CERT_VALIDATION_METHOD == "manual":
                # 手动模式下，假设证书更新成功
                logger.info("手动验证完成，证书应该已更新成功")
                return True
            else:
                # 非手动模式可以解析输出
                logger.info(result.stdout)
                # 解析输出只是为了日志记录，不再保存到JSON文件
                cert_info = parse_renewal_output(result.stdout)
                if cert_info:
                    logger.info(f"Certificate renewal information parsed: {cert_info}")
                return True
        else:
            if Config.CERT_VALIDATION_METHOD == "manual":
                logger.error("Certificate renewal failed in manual mode")
            else:
                logger.error(f"Certificate renewal failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error renewing certificate: {e}")
        return False


def parse_renewal_output(output: str) -> dict:
    """Parse certbot renewal output to extract certificate information."""
    cert_info = {}
    lines = output.split("\n")

    for line in lines:
        line = line.strip()
        if "Congratulations!" in line or "Renewal succeeded" in line:
            cert_info["status"] = "renewed"
        elif "Your certificate and chain have been saved at:" in line:
            parts = line.split(":")
            if len(parts) > 1:
                cert_info["cert_path"] = parts[1].strip()
        elif "Your key file has been saved at:" in line:
            parts = line.split(":")
            if len(parts) > 1:
                cert_info["key_path"] = parts[1].strip()
        elif "Your certificate will expire on" in line:
            parts = line.split("on")
            if len(parts) > 1:
                cert_info["expires"] = parts[1].strip()
        elif "new certificate deployed" in line.lower():
            cert_info["deployed"] = True

    return cert_info




def main() -> None:
    """Main function for renewing certificates."""
    logger.info("Starting certificate renewal check...")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    # Check if renewal is needed
    needs_renewal = check_certificate_expiry()

    if not needs_renewal:
        logger.info("Certificate does not need renewal at this time.")
        sys.exit(0)

    # Renew certificate
    logger.info("Certificate renewal needed. Starting renewal process...")
    success = renew_certificate()

    if success:
        logger.info("Certificate renewal completed successfully!")
        sys.exit(0)
    else:
        logger.error("Certificate renewal failed!")
        sys.exit(1)




if __name__ == "__main__":
    main()
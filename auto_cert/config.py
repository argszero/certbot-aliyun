"""Configuration management for auto-cert."""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for auto-cert."""

    # Alibaba Cloud credentials
    ALIBABA_CLOUD_ACCESS_KEY_ID = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    ALIBABA_CLOUD_ACCESS_KEY_SECRET = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    ALIBABA_CLOUD_REGION_ID = os.getenv("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")

    # Certificate configuration
    CERT_DOMAINS = os.getenv("CERT_DOMAINS", "example.com,*.example.com").split(",")
    CERT_EMAIL = os.getenv("CERT_EMAIL", "admin@example.com")
    CERT_STAGING = os.getenv("CERT_STAGING", "false").lower() == "true"
    CERT_VALIDATION_METHOD = os.getenv("CERT_VALIDATION_METHOD", "manual")  # manual, dns-route53, alidns, or standalone

    # SLB configuration
    SLB_INSTANCE_ID = os.getenv("SLB_INSTANCE_ID", os.getenv("SLB_INSTANCE_IP", "alb-xxxxxx"))
    SLB_LISTENER_ID = os.getenv("SLB_LISTENER_ID", "")  # Required: specific listener ID for certificate deployment
    SLB_LISTENER_PROTOCOL = os.getenv("SLB_LISTENER_PROTOCOL", "https")

    # Cron configuration
    CRON_INTERVAL_HOURS = int(os.getenv("CRON_INTERVAL_HOURS", "12"))

    # Paths
    CERT_STORAGE_PATH = Path(os.getenv("CERT_STORAGE_PATH", "./certs"))
    CERTBOT_CONFIG_DIR = Path(os.getenv("CERTBOT_CONFIG_DIR", "./certbot-config"))

    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Check required Alibaba Cloud credentials
        if not cls.ALIBABA_CLOUD_ACCESS_KEY_ID:
            errors.append("ALIBABA_CLOUD_ACCESS_KEY_ID is required")
        if not cls.ALIBABA_CLOUD_ACCESS_KEY_SECRET:
            errors.append("ALIBABA_CLOUD_ACCESS_KEY_SECRET is required")

        # Check certificate domains
        if not cls.CERT_DOMAINS:
            errors.append("CERT_DOMAINS is required")

        # Check certificate email
        if not cls.CERT_EMAIL:
            errors.append("CERT_EMAIL is required")

        # Check SLB instance ID
        if not cls.SLB_INSTANCE_ID:
            errors.append("SLB_INSTANCE_ID is required")

        # Check SLB listener ID (required for certificate deployment)
        if not cls.SLB_LISTENER_ID:
            errors.append("SLB_LISTENER_ID is required for certificate deployment")

        return errors

    @classmethod
    def get_certbot_args(cls) -> List[str]:
        """Get certbot command arguments based on configuration."""
        args = [
            "certonly",
            "--agree-tos",
            "--no-eff-email",
            "--email", cls.CERT_EMAIL,
            "--config-dir", str(cls.CERTBOT_CONFIG_DIR),
            "--work-dir", str(cls.CERTBOT_CONFIG_DIR / "work"),
            "--logs-dir", str(cls.CERTBOT_CONFIG_DIR / "logs"),
            # Use RSA key type for compatibility with Alibaba Cloud SLB
            "--key-type", "rsa",
            "--rsa-key-size", "2048",
        ]

        # Add cert name for renewal (use first domain as cert name)
        if cls.CERT_DOMAINS:
            args.extend(["--cert-name", cls.CERT_DOMAINS[0].strip()])

        # Add validation method
        if cls.CERT_VALIDATION_METHOD == "manual":
            # 手动DNS验证 - 用户需要手动添加TXT记录
            args.extend(["--manual", "--preferred-challenges", "dns-01"])
        elif cls.CERT_VALIDATION_METHOD == "dns-route53":
            # AWS Route53自动验证
            args.extend(["--authenticator", "dns-route53", "--preferred-challenges", "dns-01"])
        elif cls.CERT_VALIDATION_METHOD == "alidns":
            # 阿里云DNS自动验证 - 使用manual + hook方式，避免插件安装问题
            # 创建hook脚本路径
            hook_script = Path(__file__).parent / "alidns_hook.py"
            args.extend([
                "--manual",
                "--preferred-challenges", "dns-01",
                "--manual-auth-hook", f"uv run python {hook_script}",
                "--manual-cleanup-hook", f"uv run python {hook_script}",
                "--non-interactive"
            ])
        else:
            # 默认使用standalone HTTP验证（不支持通配符）
            args.extend(["--standalone", "--preferred-challenges", "http-01"])

        # Add staging flag if enabled
        if cls.CERT_STAGING:
            args.append("--staging")

        # Add domains
        for domain in cls.CERT_DOMAINS:
            args.extend(["-d", domain.strip()])

        return args
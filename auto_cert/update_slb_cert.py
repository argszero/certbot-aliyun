"""Certificate management and deployment for Alibaba Cloud CAS and SLB."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from alibabacloud_cas20200407.client import Client as CasClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_cas20200407 import models as cas_20200407_models
from alibabacloud_tea_util import models as util_models
from aliyunsdkalb.request.v20200616 import UpdateListenerAttributeRequest
from aliyunsdkcore.client import AcsClient

from .config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CertificateManager:
    """Alibaba Cloud CAS Certificate Manager."""

    def __init__(self):
        """Initialize CAS client with credentials."""
        self.cas_client = self._create_cas_client()

    def _create_cas_client(self) -> Optional[CasClient]:
        """Create CAS client for certificate operations."""
        try:
            config = open_api_models.Config(
                access_key_id=Config.ALIBABA_CLOUD_ACCESS_KEY_ID,
                access_key_secret=Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            )
            config.endpoint = 'cas.aliyuncs.com'
            config.region_id = Config.ALIBABA_CLOUD_REGION_ID

            return CasClient(config)

        except Exception as e:
            logger.error(f"Error creating CAS client: {e}")
            return None

    def list_uploaded_certificates(self) -> List[Dict[str, Any]]:
        """List uploaded certificates using ListUserCertificateOrder API with order_type='UPLOAD'."""
        if not self.cas_client:
            logger.error("CAS client not initialized")
            return []

        try:
            logger.info("Listing uploaded certificates...")

            request = cas_20200407_models.ListUserCertificateOrderRequest(
                order_type="UPLOAD",
                current_page=1,
                show_size=100
            )

            runtime = util_models.RuntimeOptions()
            response = self.cas_client.list_user_certificate_order_with_options(request, runtime)

            if response:
                response_dict = response.to_map() if hasattr(response, 'to_map') else {}
                body = response_dict.get('body', {})
                certificate_orders = body.get('CertificateOrderList', [])
                total_count = body.get('TotalCount', 0)

                logger.info(f"Found {total_count} uploaded certificate(s)")
                return certificate_orders
            else:
                logger.error("Empty response from ListUserCertificateOrder API")
                return []

        except Exception as e:
            logger.error(f"Error listing uploaded certificates: {e}")
            return []

    def find_certificate_for_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Find uploaded certificate for a specific domain."""
        certificates = self.list_uploaded_certificates()

        for cert in certificates:
            if isinstance(cert, dict):
                cert_name = cert.get('Name')
                common_name = cert.get('CommonName')
                sans = cert.get('Sans', '')

                # Check if domain matches certificate name, common name, or SANs
                if (cert_name and domain in cert_name) or \
                   (common_name and domain in common_name) or \
                   (sans and domain in sans):
                    logger.info(f"Found certificate for domain '{domain}': ID={cert.get('CertificateId')}, Name={cert_name}")
                    return cert

        logger.info(f"No certificate found for domain: {domain}")
        return None

    def delete_certificate(self, cert_id: str) -> bool:
        """Delete a certificate using DeleteUserCertificate API."""
        if not self.cas_client:
            logger.error("CAS client not initialized")
            return False

        try:
            logger.info(f"Deleting certificate: {cert_id}")

            request = cas_20200407_models.DeleteUserCertificateRequest(
                cert_id=cert_id
            )

            runtime = util_models.RuntimeOptions()
            response = self.cas_client.delete_user_certificate_with_options(request, runtime)

            if response:
                logger.info(f"Successfully deleted certificate: {cert_id}")
                return True
            else:
                logger.error("Empty response from DeleteUserCertificate API")
                return False

        except Exception as e:
            logger.error(f"Error deleting certificate {cert_id}: {e}")
            return False

    def upload_certificate(self, name: str, cert_content: str, key_content: str) -> Optional[Dict[str, Any]]:
        """Upload a certificate using UploadUserCertificate API.

        Returns a dictionary with certificate information including:
        - cert_id: The certificate ID in CAS
        - resource_id: The resource ID for use with ALB/SLB
        """
        if not self.cas_client:
            logger.error("CAS client not initialized")
            return None

        try:
            logger.info(f"Uploading certificate: {name}")

            request = cas_20200407_models.UploadUserCertificateRequest(
                name=name,
                cert=cert_content,
                key=key_content
            )

            runtime = util_models.RuntimeOptions()
            response = self.cas_client.upload_user_certificate_with_options(request, runtime)

            if response:
                response_dict = response.to_map() if hasattr(response, 'to_map') else {}
                body = response_dict.get('body', {})
                cert_id = body.get('CertId')
                resource_id = body.get('ResourceId')

                if cert_id:
                    logger.info(f"Successfully uploaded certificate: {name}, ID: {cert_id}, Resource ID: {resource_id}")
                    return {
                        "cert_id": str(cert_id),
                        "resource_id": str(resource_id) if resource_id else None,
                        "name": name
                    }
                else:
                    logger.error("No CertId in upload response")
                    return None
            else:
                logger.error("Empty response from UploadUserCertificate API")
                return None

        except Exception as e:
            logger.error(f"Error uploading certificate {name}: {e}")
            return None

    def read_certificate_files(self, cert_path: str, key_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Read certificate and private key files."""
        try:
            with open(cert_path, 'r') as f:
                cert_content = f.read()

            with open(key_path, 'r') as f:
                key_content = f.read()

            return cert_content, key_content
        except Exception as e:
            logger.error(f"Error reading certificate files: {e}")
            return None, None


class SLBManager:
    """Alibaba Cloud SLB/ALB Manager."""

    def __init__(self):
        """Initialize ALB client with credentials."""
        self.alb_client = self._create_alb_client()

    def _create_alb_client(self) -> Optional[AcsClient]:
        """Create ALB client for load balancer operations."""
        try:
            client = AcsClient(
                ak=Config.ALIBABA_CLOUD_ACCESS_KEY_ID,
                secret=Config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
                region_id=Config.ALIBABA_CLOUD_REGION_ID
            )
            logger.info("Successfully created ALB client")
            return client
        except Exception as e:
            logger.error(f"Error creating ALB client: {e}")
            return None

    def update_listener_certificate(self, listener_id: str, certificate_id: str) -> bool:
        """Update HTTPS listener certificate on ALB."""
        if not self.alb_client:
            logger.error("ALB client not initialized")
            return False

        try:
            logger.info(f"Updating ALB listener {listener_id} with certificate {certificate_id}")

            # Create request
            request = UpdateListenerAttributeRequest.UpdateListenerAttributeRequest()
            request.set_ListenerId(listener_id)

            # For ALB, we need to set the certificate ID in the Certificates field
            # The format should be: [{"CertificateId": "cert-id"}]
            certificates = [{"CertificateId": certificate_id}]
            request.set_Certificates(certificates)

            # Send request
            response = self.alb_client.do_action_with_exception(request)

            if response:
                logger.info(f"Successfully updated ALB listener {listener_id} with certificate {certificate_id}")
                return True
            else:
                logger.error(f"Empty response from ALB API for listener {listener_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating ALB listener {listener_id}: {e}")
            return False

    def get_listener_id(self, load_balancer_id: str) -> Optional[str]:
        """Get the listener ID for the load balancer.

        Priority:
        1. Use SLB_LISTENER_ID from configuration if provided
        2. Otherwise, try to query ALB API to find matching listener
        3. Return None if cannot determine listener ID
        """
        # First, check if listener ID is provided in configuration
        if Config.SLB_LISTENER_ID:
            logger.info(f"Using configured listener ID: {Config.SLB_LISTENER_ID}")
            return Config.SLB_LISTENER_ID

        logger.warning(f"No listener ID configured for load balancer {load_balancer_id}")
        logger.warning("To enable SLB certificate deployment, please:")
        logger.warning("1. Find your listener ID in ALB console")
        logger.warning("2. Set SLB_LISTENER_ID in .env file")
        logger.warning("3. Common listener ID pattern: lsr-xxxxxx")

        # In a production implementation, you would query the ALB API here:
        # 1. Call DescribeLoadBalancerAttribute to get listener information
        # 2. Find the HTTPS listener
        # 3. Return its listener ID

        return None


def get_latest_certificate_paths() -> Tuple[Optional[str], Optional[str]]:
    """Get paths to the latest certificate and private key."""
    try:
        # Look for certificate files in certbot config directory
        certbot_live_dir = Path(Config.CERTBOT_CONFIG_DIR) / "live"

        if not certbot_live_dir.exists():
            logger.error(f"Certbot live directory not found: {certbot_live_dir}")
            return None, None

        # Find the latest certificate directory (should be based on first domain)
        cert_domains = Config.CERT_DOMAINS
        if not cert_domains:
            logger.error("No domains configured in CERT_DOMAINS")
            return None, None

        # Use the first domain to find the certificate directory
        primary_domain = cert_domains[0].strip()
        cert_dir = certbot_live_dir / primary_domain

        if not cert_dir.exists():
            # Try to find any certificate directory
            cert_dirs = list(certbot_live_dir.glob("*"))
            if not cert_dirs:
                logger.error(f"No certificate directories found in {certbot_live_dir}")
                return None, None

            # Use the first directory found
            cert_dir = cert_dirs[0]
            logger.info(f"Using certificate directory: {cert_dir.name}")

        # Check for required files
        cert_path = cert_dir / "fullchain.pem"
        key_path = cert_dir / "privkey.pem"

        if not cert_path.exists():
            logger.error(f"Certificate file not found: {cert_path}")
            return None, None

        if not key_path.exists():
            logger.error(f"Private key file not found: {key_path}")
            return None, None

        logger.info(f"Found certificate: {cert_path}")
        logger.info(f"Found private key: {key_path}")

        return str(cert_path), str(key_path)

    except Exception as e:
        logger.error(f"Error getting certificate paths: {e}")
        return None, None


def save_deployment_info(
    load_balancer_id: str,
    listener_id: str,
    primary_cert_id: str,
    all_cert_ids: List[str]
) -> None:
    """Save SLB deployment information to file."""
    try:
        deployment_info = {
            "load_balancer_id": load_balancer_id,
            "listener_id": listener_id,
            "primary_certificate_id": primary_cert_id,
            "all_certificate_ids": all_cert_ids,
            "deployed_at": datetime.now().isoformat(),
            "domains": Config.CERT_DOMAINS
        }

        deployment_path = Config.CERT_STORAGE_PATH / "slb_deployment_info.json"
        with open(deployment_path, "w") as f:
            json.dump(deployment_info, f, indent=2)

        logger.info(f"Deployment information saved to {deployment_path}")

    except Exception as e:
        logger.warning(f"Could not save deployment information: {e}")


def manage_certificates() -> bool:
    """Main function to manage certificates based on CERT_DOMAINS and deploy to SLB."""
    logger.info("Starting certificate management and SLB deployment...")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    # Get certificate paths
    cert_path, key_path = get_latest_certificate_paths()
    if not cert_path or not key_path:
        logger.error("Could not get certificate paths. Please run apply-cert or renew-cert first.")
        return False

    logger.info(f"Certificate path: {cert_path}")
    logger.info(f"Private key path: {key_path}")

    # Initialize certificate manager
    try:
        cert_manager = CertificateManager()
    except Exception as e:
        logger.error(f"Error initializing certificate manager: {e}")
        return False

    # Initialize SLB manager
    try:
        slb_manager = SLBManager()
    except Exception as e:
        logger.error(f"Error initializing SLB manager: {e}")
        return False

    # Read certificate files
    cert_content, key_content = cert_manager.read_certificate_files(cert_path, key_path)
    if not cert_content or not key_content:
        logger.error("Failed to read certificate files")
        return False

    # Get SLB configuration
    load_balancer_id = Config.SLB_INSTANCE_ID

    logger.info(f"Load balancer ID: {load_balancer_id}")

    # Try to get listener ID
    listener_id = slb_manager.get_listener_id(load_balancer_id)
    if not listener_id:
        logger.warning(f"Could not determine listener ID for load balancer {load_balancer_id}")
        logger.warning("Certificate will be uploaded to CAS but not deployed to SLB")
        # We'll still upload certificates to CAS, but skip SLB deployment

    # Process certificates for all domains
    uploaded_cert_infos = []
    success = True
    processed_cert_ids = set()  # Track certificates we've already processed

    # First, find all existing certificates that cover our domains
    existing_certs = []
    for domain in Config.CERT_DOMAINS:
        domain = domain.strip()
        if not domain:
            continue

        existing_cert = cert_manager.find_certificate_for_domain(domain)
        if existing_cert:
            cert_id = existing_cert.get('CertificateId')
            if cert_id and cert_id not in processed_cert_ids:
                existing_certs.append(existing_cert)
                processed_cert_ids.add(cert_id)

    # Delete all existing certificates
    for cert in existing_certs:
        cert_id = cert.get('CertificateId')
        if cert_id:
            logger.info(f"Deleting existing certificate: {cert_id}")
            if cert_manager.delete_certificate(str(cert_id)):
                logger.info(f"Successfully deleted certificate: {cert_id}")
            else:
                logger.warning(f"Failed to delete certificate: {cert_id}")
                # Continue anyway to try uploading new one

    # Upload new certificate for all domains
    # Create a single certificate name that includes all domains
    domain_list = [d.strip() for d in Config.CERT_DOMAINS if d.strip()]
    cert_name = f"{'-'.join(domain_list[:2])}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if len(domain_list) > 2:
        cert_name += f"-and-{len(domain_list)-2}-more"

    logger.info(f"Uploading certificate for domains: {', '.join(domain_list)}")
    cert_info = cert_manager.upload_certificate(cert_name, cert_content, key_content)

    if cert_info:
        cert_id = cert_info.get('cert_id')
        resource_id = cert_info.get('resource_id')
        logger.info(f"Successfully uploaded certificate: CAS ID={cert_id}, Resource ID={resource_id}")
        uploaded_cert_infos.append(cert_info)
    else:
        logger.error("Failed to upload certificate")
        success = False

    # Step 5: Deploy certificates to SLB if we have a listener ID
    if listener_id and uploaded_cert_infos:
        logger.info(f"\nDeploying certificates to SLB listener {listener_id}...")

        # For ALB, we need to use the resource_id (not cert_id)
        # Get the last certificate's resource_id (most recent upload)
        primary_cert_info = uploaded_cert_infos[-1] if uploaded_cert_infos else None

        if primary_cert_info:
            resource_id = primary_cert_info.get('resource_id')
            cert_id = primary_cert_info.get('cert_id')

            if resource_id:
                # Try with resource_id first (this is what ALB expects)
                if slb_manager.update_listener_certificate(listener_id, resource_id):
                    logger.info(f"Successfully deployed certificate (Resource ID: {resource_id}) to SLB listener {listener_id}")
                else:
                    # If resource_id fails, try with cert_id as fallback
                    logger.warning(f"Resource ID {resource_id} failed, trying with CAS ID {cert_id}...")
                    if slb_manager.update_listener_certificate(listener_id, cert_id):
                        logger.info(f"Successfully deployed certificate (CAS ID: {cert_id}) to SLB listener {listener_id}")
                    else:
                        logger.error(f"Failed to deploy certificate to SLB listener {listener_id}")
                        success = False

                # Save deployment information
                all_cert_ids = [info.get('cert_id') for info in uploaded_cert_infos if info.get('cert_id')]
                save_deployment_info(load_balancer_id, listener_id, cert_id, all_cert_ids)
            else:
                logger.warning(f"No resource_id available for certificate {cert_id}, trying with CAS ID...")
                if cert_id and slb_manager.update_listener_certificate(listener_id, cert_id):
                    logger.info(f"Successfully deployed certificate (CAS ID: {cert_id}) to SLB listener {listener_id}")

                    # Save deployment information
                    all_cert_ids = [info.get('cert_id') for info in uploaded_cert_infos if info.get('cert_id')]
                    save_deployment_info(load_balancer_id, listener_id, cert_id, all_cert_ids)
                else:
                    logger.error(f"Failed to deploy certificate to SLB listener {listener_id}")
                    success = False
        else:
            logger.warning("No certificate information available for SLB deployment")
    elif not listener_id:
        logger.info("Skipping SLB deployment (no listener ID available)")
    elif not uploaded_cert_infos:
        logger.warning("No certificates were uploaded, skipping SLB deployment")

    return success


def main() -> None:
    """Main entry point."""
    success = manage_certificates()

    if success:
        logger.info("Certificate management completed successfully!")
        sys.exit(0)
    else:
        logger.error("Certificate management failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
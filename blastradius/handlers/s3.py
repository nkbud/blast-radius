"""S3 handler for reading Terraform state files from S3."""

import json
import logging
import os
import time
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


logger = logging.getLogger(__name__)


class S3StateReader:
    """Handles reading Terraform state files from S3."""
    
    def __init__(self):
        """Initialize S3 client with environment configuration."""
        self.bucket = os.environ.get('S3_BUCKET')
        self.region = os.environ.get('S3_REGION', 'us-east-1')
        self.refresh_interval = int(os.environ.get('STATE_REFRESH_INTERVAL', '300'))  # 5 minutes default
        
        if not self.bucket:
            raise ValueError("S3_BUCKET environment variable is required")
            
        try:
            self.s3_client = boto3.client('s3', region_name=self.region)
            logger.info(f"Initialized S3 client for bucket: {self.bucket}, region: {self.region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Ensure IRSA is configured or AWS credentials are available.")
            raise
            
        self._state_cache = {}
        self._last_refresh = {}
    
    def is_s3_enabled(self) -> bool:
        """Check if S3 mode is enabled."""
        return bool(self.bucket)
    
    def get_state_file(self, key: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get Terraform state file from S3.
        
        Args:
            key: S3 key for the state file
            force_refresh: Force refresh even if within refresh interval
            
        Returns:
            Parsed state file content or None if not found
        """
        if not self.is_s3_enabled():
            return None
            
        current_time = time.time()
        
        # Check if we have a cached version and it's still fresh
        if not force_refresh and key in self._state_cache:
            last_refresh = self._last_refresh.get(key, 0)
            if current_time - last_refresh < self.refresh_interval:
                logger.debug(f"Using cached state for key: {key}")
                return self._state_cache[key]
        
        try:
            logger.info(f"Fetching state file from S3: s3://{self.bucket}/{key}")
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            
            # Parse the state file
            state_data = json.loads(content)
            
            # Redact sensitive attributes
            redacted_state = self._redact_sensitive_attributes(state_data)
            
            # Cache the result
            self._state_cache[key] = redacted_state
            self._last_refresh[key] = current_time
            
            logger.info(f"Successfully loaded and cached state file: {key}")
            return redacted_state
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"State file not found: s3://{self.bucket}/{key}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket not found: {self.bucket}")
            else:
                logger.error(f"Error fetching state file from S3: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing state file JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching state file: {e}")
            return None
    
    def _redact_sensitive_attributes(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive attributes from state data.
        
        Args:
            state_data: Original state data
            
        Returns:
            State data with sensitive attributes redacted
        """
        # Define sensitive attribute patterns
        sensitive_patterns = [
            'password', 'secret', 'token', 'key', 'credential',
            'private_key', 'certificate', 'auth', 'api_key'
        ]
        
        def redact_recursive(obj, path=""):
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    
                    # Check if this key contains sensitive information
                    is_sensitive = any(pattern.lower() in k.lower() for pattern in sensitive_patterns)
                    
                    if is_sensitive and isinstance(v, str):
                        result[k] = "[REDACTED]"
                        logger.debug(f"Redacted sensitive attribute: {current_path}")
                    else:
                        result[k] = redact_recursive(v, current_path)
                return result
            elif isinstance(obj, list):
                return [redact_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
            else:
                return obj
        
        return redact_recursive(state_data)
    
    def list_available_states(self) -> list:
        """
        List available Terraform state files in the S3 bucket.
        
        Returns:
            List of S3 keys for .tfstate files
        """
        if not self.is_s3_enabled():
            return []
            
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix='',  # List all objects
                MaxKeys=1000
            )
            
            state_files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('.tfstate') or 'terraform.tfstate' in key:
                        state_files.append(key)
            
            logger.info(f"Found {len(state_files)} state files in S3")
            return sorted(state_files)
            
        except ClientError as e:
            logger.error(f"Error listing S3 objects: {e}")
            return []
    
    def clear_cache(self):
        """Clear the state file cache."""
        self._state_cache.clear()
        self._last_refresh.clear()
        logger.info("State file cache cleared")


# Global instance
s3_state_reader = S3StateReader() if os.environ.get('S3_BUCKET') else None
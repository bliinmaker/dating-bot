import boto3
from botocore.client import Config
import config
import logging
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=f"{'https' if config.S3_SECURE else 'http'}://{config.S3_ENDPOINT}",
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        self.bucket_name = config.S3_BUCKET_NAME
        self._ensure_bucket_exists()
        logger.info(f"S3 client initialized with endpoint: {config.S3_ENDPOINT}")

    def _ensure_bucket_exists(self):
        """Create the bucket if it doesn't exist"""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except:
            try:
                self.s3.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created S3 bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Error creating S3 bucket: {e}")

    def upload_photo(self, photo_data: bytes, content_type: str = 'image/jpeg') -> Optional[str]:
        """Upload a photo to S3 and return the path"""
        try:
            file_name = f"photos/{str(uuid.uuid4())}.jpg"
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=photo_data,
                ContentType=content_type
            )
            logger.info(f"Uploaded photo to S3: {file_name}")
            return file_name
        except Exception as e:
            logger.error(f"Error uploading photo to S3: {e}")
            return None

    def get_photo_url(self, file_path: str) -> Optional[str]:
        """Generate a pre-signed URL for a photo"""
        try:
            endpoint = config.S3_ENDPOINT
            protocol = 'https' if config.S3_SECURE else 'http'

            url = f"{protocol}://{endpoint}/{self.bucket_name}/{file_path}"

            logger.debug(f"Generated photo URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Error generating URL for {file_path}: {e}")
            return None

    def delete_photo(self, file_path: str) -> bool:
        """Delete a photo from S3"""
        try:
            self.s3.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            logger.info(f"Deleted photo from S3: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting photo from S3: {e}")
            return False
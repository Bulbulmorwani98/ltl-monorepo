import boto3
from datetime import datetime
import os
import mimetypes
from urllib.parse import urlparse,unquote
import uuid
class S3Uploader:
    def __init__(self):
        """Initialize the S3 client with the provided credentials."""
        self.bucket_name = "video-verify-metadata-processed-files"
        self.region = "us-west-2"
        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv("REGION_NAME"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def upload_image(self, local_image_path, user_email, original_filename):
        """Uploads an image to S3 and returns the file URL."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        s3_key = f"{user_email}/{original_filename}"

        # Guess content type based on file extension
        content_type, _ = mimetypes.guess_type(local_image_path)

        try:
            self.s3_client.upload_file(
                Filename=local_image_path,
                Bucket=self.bucket_name,
                Key=s3_key,
                ExtraArgs={
                    
                    'ContentType': content_type or 'application/octet-stream',
                    'ContentDisposition': f'attachment; filename="{original_filename}"'
                }
            )
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            return url
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            return None
        

    def generate_download_url(self, s3_key, original_filename, expires_in=3600):
        return self.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': s3_key,
                'ResponseContentDisposition': f'attachment; filename="{original_filename}"'
            },
            ExpiresIn=expires_in
        )
        
    def upload_profile_image(self, local_image_path, user_email, original_filename):
         """Uploads an image to S3 and returns the file URL."""
         timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
         s3_key = f"{user_email}_profile/{original_filename}"
 
         try:
             self.s3_client.upload_file(
                 Filename=local_image_path,
                 Bucket=self.bucket_name,
                 Key=s3_key,
                 ExtraArgs={'ContentType': 'image/jpeg'}
             )
             url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
             return url
         except Exception as e:
             print(f"Error uploading file: {str(e)}")
             return None
        
    def upload_video(self, local_video_path, user_email, original_filename):
        """Uploads a video to S3 and returns the file URL."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        s3_key = f"{user_email}/{original_filename}"

        # Guess content type based on file extension
        content_type, _ = mimetypes.guess_type(local_video_path)

        try:
            self.s3_client.upload_file(
                Filename=local_video_path,
                Bucket=self.bucket_name,
                Key=s3_key,
                ExtraArgs={
                    'ContentType': content_type or 'application/octet-stream',
                    'ContentDisposition': f'attachment; filename="{original_filename}"'
                }
            )
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            return url
        except Exception as e:
            print(f"Error uploading video: {str(e)}")
            return None

    # from urllib.parse import urlparse, unquote

    def delete_image(self, s3_url):
        """Deletes an image from S3 given its URL."""
        try:
            parsed_url = urlparse(s3_url)
            s3_key = unquote(parsed_url.path.lstrip("/"))  # Decode special characters like '%40' to '@'
            print(f"Extracted S3 Key: {s3_key}")  # Debugging output

            response = self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            print(f"S3 Delete Response: {response}")  # Print response from S3

            print(f"Deleted image from S3: {s3_url}")
            return True
        except Exception as e:
            print(f"Error deleting image: {str(e)}")
            return False



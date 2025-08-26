# app_name/tasks.py
import base64
import os
import json
from io import BytesIO
from datetime import datetime
from celery import shared_task
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.utils import timezone

from .models import OrgUser, ImageStatus, Usercontent, TaskLog
from .helpers import c2pa_utils
from .helpers.s3_helpers import S3Uploader
import asyncio
s3_obj = S3Uploader()

# @shared_task(bind=True)
def image_processing(self, user_id, user_email, filename, file_data, params):
    try:
        file_bytes = base64.b64decode(file_data)
        file_stream = BytesIO(file_bytes)
        file_storage = InMemoryUploadedFile(file_stream, None, filename, None, len(file_bytes), None)

        try:
            db_user = OrgUser.objects.get(id=user_id)
        except OrgUser.DoesNotExist:
            # logger.error(f"OrgUser with id {user_id} does not exist")
            return "User not found."

        download_link, image_name = asyncio.run(c2pa_utils.process_file(file_storage, **params))

        s3_url = s3_obj.upload_image(local_image_path=download_link, user_email=user_email, original_filename=filename)

        # with transaction.atomic():
        image_status, _ = ImageStatus.objects.update_or_create(
            user_id=db_user.id,
            image_name=filename,
            defaults={
                'image_status': 'succeeded',
                'image_url': s3_url,
                'upload_date': timezone.now(),  # ✅ FIXED HERE
                'meta_data': json.dumps(params),
            }
        )

        existing_entry = Usercontent.objects.filter(user_id=db_user.id, image_url=s3_url).first()
        if existing_entry:
            existing_entry.image_url = s3_url
            existing_entry.meta_data = json.dumps(params)
            existing_entry.save()
        else:
            new_entry = Usercontent(
                user=db_user,  # ✅ FIXED HERE
                image_url=s3_url,
                meta_data=json.dumps(params)
            )
            new_entry.save()
        
        # ✅ Safe cleanup
        if download_link and os.path.exists(download_link):
            os.remove(download_link)
        if image_name and os.path.exists(f"processed_files/{image_name}"):
            os.remove(f"processed_files/{image_name}")

        return "Task completed successfully."

    except Exception as e:
        # logger.exception(f"Failed to enqueue task for file {filename}: {e}")
        return f"Task failed: {e}"

    except Exception as e:

        # Update the ImageStatus record to 'failed'
        try:
            ImageStatus.objects.filter(user_id=user_id, image_name=filename).update(
                image_status='failed',
                image_url=s3_url,
                meta_data=json.dumps(params),
                upload_date=datetime.utcnow()
            )

            Usercontent.objects.filter(user_id=user_id, image_url=s3_url).delete()

        except Exception as db_err:
            print(f"Error updating image status to failed: {db_err}")

        #  Cleanup any files if they exist
        if os.path.exists(download_link):
            os.remove(download_link)
        if os.path.exists(f"processed_files/{image_name}"):
            os.remove(f"processed_files/{image_name}")

        # #  Log the task failure
        # TaskLog.objects.create(
        #     task_id=self.request.id,
        #     status='FAILED',
        #     error_message=str(e)
        # )

        raise e


# @shared_task(bind=True)
def video_processing(self, user_id, user_email, filename, file_data, params):
    download_link = None
    thumbnail_path = None
    image_name = None

    try:
        file_bytes = base64.b64decode(file_data)
        file_stream = BytesIO(file_bytes)
        file_storage = InMemoryUploadedFile(file_stream, None, filename, None, len(file_bytes), None)

        db_user = OrgUser.objects.get(id=user_id)

        # 1. Process file (generate download_link and image_name)
        download_link, image_name = asyncio.run(c2pa_utils.process_file(file_storage, **params))

        # 2. Upload video to S3
        s3_url = s3_obj.upload_video(local_video_path=download_link, user_email=user_email, original_filename=filename)


        # 4. Now run thumbnail logic (after video is already saved)
        thumbnail_filename = f"thumbnail_{filename.rsplit('.', 1)[0]}.jpg"
        thumbnail_dir = "thumbnails"
        os.makedirs(thumbnail_dir, exist_ok=True)  # ✅ Ensure folder exists before saving
        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
        s3_obj.create_video_thumbnail(video_path=download_link, thumbnail_path=thumbnail_path)
        thumbnail_s3_url = s3_obj.upload_video(local_video_path=thumbnail_path, user_email=user_email, original_filename=thumbnail_filename)


        # 5. Save video metadata to DB (before thumbnail processing)
        # with transaction.atomic():
        ImageStatus.objects.update_or_create(
            user_id=db_user.id,
            image_name=filename,
            defaults={
                'image_status': 'succeeded',
                'image_url': s3_url,
                'upload_date': datetime.utcnow(),
                'meta_data': json.dumps(params),
                'thumbnail_url': thumbnail_s3_url,
            }
        )

        Usercontent.objects.update_or_create(
            user_id=db_user.id,
            video_url=s3_url,
            defaults={
                'meta_data': json.dumps(params),
                'thumbnail_url': thumbnail_s3_url,
            }
        )

        if os.path.exists(download_link):
            os.remove(download_link)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if os.path.exists(f"processed_files/{image_name}"):
            os.remove(f"processed_files/{image_name}")

        return "Task completed successfully."

    except Exception as e:
        print("Exception occurred:", str(e))

        try:
            ImageStatus.objects.filter(user_id=user_id, image_name=filename).update(
                image_status='failed',
                image_url=s3_url,
                thumbnail_url=None,
                upload_date=datetime.utcnow()
            )

            Usercontent.objects.filter(user_id=user_id, video_url=s3_url).delete()

             # ✅ If video URL exists, ensure thumbnail_url is set to None
            if s3_url:
                Usercontent.objects.filter(user_id=user_id, video_url=s3_url).update(
                    thumbnail_url=None
                )
        except Exception as db_err:
            print(f"Error updating image status to failed: {db_err}")

        # Cleanup on failure
        if download_link and os.path.exists(download_link):
            os.remove(download_link)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if image_name and os.path.exists(f"processed_files/{image_name}"):
            os.remove(f"processed_files/{image_name}")

        # TaskLog.objects.create(
        #     # task_id=self.request.id,
        #     status='FAILED',
        #     error_message=str(e)
        # )

        raise e
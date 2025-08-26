from celery import Celery
import models as user_models
from models import db
# Example long-running task
from celery.signals import task_prerun, task_success, task_failure
# Define Celery tasks here
from datetime import datetime
import asyncio
from sqlalchemy import cast, Text
import metadata_modifier.c2pa_utils as c2pa_utils
from helpers.s3_helpers import S3Uploader
s3_obj = S3Uploader()
import os
import json
import base64
from io import BytesIO
from werkzeug.datastructures import FileStorage
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - Line: %(lineno)d - %(message)s",
    handlers=[logging.FileHandler("c2pa_utils.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def create_celery_app(flask_app):
    """Create and configure a Celery app using Flask app context."""
    celery_app = Celery(
        flask_app.name,
        broker=flask_app.config['broker_url'],
        backend=flask_app.config['result_backend']
    )
    celery_app.conf.update(flask_app.config)

    # Enable Flask context within tasks
    TaskBase = celery_app.Task
    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app



def log_task_status(task_id, status, result=None, error_message=None):
    """Helper function to log task status into the database."""
    task_log = user_models.TaskLog.query.filter_by(task_id=task_id).first()
    if not task_log:
        task_log = user_models.TaskLog(task_id=task_id, status=status)
        db.session.add(task_log)
    else:
        task_log.status = status
        task_log.result = result
        task_log.error_message = error_message
    db.session.commit()



@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, **kwargs):
    from app import app  # Import inside to avoid circular import
    with app.app_context():
        log_task_status(task_id, status='RUNNING')


@task_success.connect
def task_success_handler(sender=None, result=None, task_id=None, **kwargs):
    from app import app
    with app.app_context():
        task_id = task_id or getattr(sender, 'request', {}).get('id', None)
         # Get task_id from kwargs or sender (task instance)
        if task_id:  # Only log if task_id is valid
            log_task_status(task_id, status='SUCCESS', result=result)


@task_failure.connect
def task_failure_handler(sender=None, exception=None, task_id=None, **kwargs):
    from app import app
    with app.app_context():
        task_id = task_id or getattr(sender, 'request', {}).get('id', None)
        # Get task_id from kwargs or sender (task instance)
        if task_id:  # Only log if task_id is valid
            log_task_status(task_id, status='FAILED', error_message=str(exception))


# celery -A app.celery_app worker --loglevel=info  (run this command in terminal)
def register_tasks(celery_app):
    """Register Celery tasks here."""
    @celery_app.task(bind=True)
    def image_processing(self, user_email, filename, file_data, params):
        try:
            file_bytes = base64.b64decode(file_data)
            file_stream = BytesIO(file_bytes)
            file_storage = FileStorage(stream=file_stream, filename=filename)
            db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
            """Simulate a long-running task."""
            download_link , image_name = asyncio.run(c2pa_utils.process_file(file_storage, **params))
            # Upload to S3
            s3_url = s3_obj.upload_image(local_image_path=download_link,user_email=user_email,original_filename=filename)

            # Check if ImageStatus already exists
            existing_image_status = db.session.query(user_models.ImageStatus).filter_by(
                user_id=db_user.id,
                image_name=filename
            ).first()


            if existing_image_status:
                existing_image_status.image_status = 'succeeded'
                existing_image_status.image_url = s3_url
                existing_image_status.upload_date = datetime.utcnow()
            else:
                # Insert new record
                imagestatus = user_models.ImageStatus(
                    image_name=filename,
                    image_url=s3_url,
                    image_status='succeeded',
                    user_id=db_user.id
                )
                db.session.add(imagestatus)
            db.session.commit()

            serialized_params = json.dumps(params, sort_keys=True)

            # Get all possible matches
            all_user_content = db.session.query(user_models.Usercontent).filter(
                user_models.Usercontent.user_id == db_user.id,
                user_models.Usercontent.image_url == s3_url
            ).all()

            # Compare JSON dicts
            existing_content = None
            for uc in all_user_content:
                try:
                    if json.loads(uc.meta_data) == params or json.loads(uc.meta_data) != params:
                        existing_content = uc
                        break
                except Exception:
                    continue

            # Create or update accordingly
            if existing_content:
                existing_content.image_url = s3_url
                existing_content.meta_data=json.dumps(params)
            else:
                new_product = user_models.Usercontent(
                    user_id=db_user.id,
                    image_url=s3_url,
                    meta_data=serialized_params
                )
                db.session.add(new_product)

            db.session.commit()

            if os.path.exists(download_link):
                os.remove(download_link)
            if os.path.exists(f"processed_files/{image_name}"):
                os.remove(f"processed_files/{image_name}")
    
            return f"Task completed in seconds"
        except Exception as e:
            return {"error": str(e)}
        
    @celery_app.task(bind=True)
    def video_processing(self, user_email, filename, file_data, params):
        file_bytes = base64.b64decode(file_data)
        file_stream = BytesIO(file_bytes)
        file_storage = FileStorage(stream=file_stream, filename=filename)
        db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
        """Simulate a long-running task."""
        download_link , image_name = asyncio.run(c2pa_utils.process_file(file_storage, **params))
        # Upload to S3
        s3_url = s3_obj.upload_video(local_video_path=download_link,user_email=user_email,original_filename=filename)

        thumbnail_filename = f"thumbnail_{filename.rsplit('.', 1)[0]}.jpg"
        thumbnail_path = os.path.join("thumbnails", thumbnail_filename)
        os.makedirs("thumbnails", exist_ok=True)

        s3_obj.create_video_thumbnail(video_path=download_link, thumbnail_path=thumbnail_path)

        thumbnail_s3_url = s3_obj.upload_video(local_video_path=thumbnail_path, user_email=user_email, original_filename=thumbnail_filename)

        # Check if ImageStatus already exists
        existing_image_status = db.session.query(user_models.ImageStatus).filter_by(
            user_id=db_user.id,
            image_name=filename
        ).first()


        if existing_image_status:
            existing_image_status.image_status = 'succeeded'
            existing_image_status.image_url = s3_url
            existing_image_status.upload_date = datetime.utcnow()
        else:
            # Insert new record
            imagestatus = user_models.ImageStatus(
                image_name=filename,
                image_url=s3_url,
                image_status='succeeded',
                user_id=db_user.id
            )
            db.session.add(imagestatus)
        db.session.commit()

        serialized_params = json.dumps(params, sort_keys=True)

        # Get all possible matches
        all_user_content = db.session.query(user_models.Usercontent).filter(
            user_models.Usercontent.user_id == db_user.id,
            user_models.Usercontent.video_url == s3_url
        ).all()

        # Compare JSON dicts
        existing_content = None
        for uc in all_user_content:
            try:
                if json.loads(uc.meta_data) == params or json.loads(uc.meta_data) != params:
                    existing_content = uc
                    break
            except Exception:
                continue

        # Create or update accordingly
        if existing_content:
            existing_content.video_url = s3_url
            existing_content.meta_data = json.dumps(params)
            existing_content.thumbnail_url = thumbnail_s3_url
        else:
            new_product = user_models.Usercontent(
                user_id=db_user.id,
                video_url=s3_url,
                thumbnail_url=thumbnail_s3_url,
                meta_data=serialized_params
            )
            db.session.add(new_product)

        db.session.commit()
        
        if os.path.exists(download_link):
            os.remove(download_link)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if os.path.exists(f"processed_files/{image_name}"):
            os.remove(f"processed_files/{image_name}")
   
        return f"Task completed in seconds"

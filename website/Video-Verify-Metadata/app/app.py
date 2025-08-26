from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    render_template,
    redirect,
    url_for,
    session,
)
import base64
from flask_cors import CORS
import requests
import io
from dotenv import load_dotenv
import os
import stripe
import asyncio
from sqlalchemy import or_
import metadata_modifier.c2pa_utils as c2pa_utils
# from metadata_modifier.routes import metadata_modifier_bp # commenting this out while checking that killing this worked.
import logging
from collections import OrderedDict
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload,aliased
from send_email import send_email
from urllib.parse import urlparse, unquote


from flask_migrate import Migrate
from models import db
import models as user_models
from datetime import datetime, timedelta, timezone
from helpers.stripe_helper import StripeSubscriptionManager
from helpers import utils
from helpers.s3_helpers import S3Uploader
from celery_worker import create_celery_app , register_tasks
from werkzeug.datastructures import FileStorage
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
import json
# from auth import auth_bp #killing auth.py.  will check that this works and then delete these lines.
# from ltl_db import test_db_connection, get_db_session, placeholder_db_call # Need to implement db stuff, do that after we are the authentication stuff.
from authlib.integrations.flask_client import OAuth
from functools import wraps

# Need to implement Stripe support, do that after we are the authentication stuff, then probably the db stuff.

# Determine the environment and load the appropriate .env file.  The ecs task-defintion.json defines the prod env for the container's prod deployment.
# env = os.getenv('ENV')
# if env == 'prod':
#     load_dotenv('/app/prod.env')
# else:
#     load_dotenv('/app/dev.env')

env = os.getenv('ENV')
env = 'prod'
if env == 'prod':
    load_dotenv('prod.env')
else:
    load_dotenv('/app/dev.env')

s3_uploader = S3Uploader()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - Line: %(lineno)d - %(message)s",
    handlers=[logging.FileHandler("c2pa_utils.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logger.info(f"Environment: {env}")
if os.getenv("USING_DEV_ENV_FILE") == "True":
    logger.debug("Using dev.env file")
elif os.getenv("USING_PROD_ENV_FILE") == "True":
    logger.debug("Using prod.env file")
else:
    logger.debug("Not using any .env file")

app = Flask(__name__, static_folder="templates/assets", static_url_path="/assets")
app.config.update(
    SQLALCHEMY_DATABASE_URI=os.getenv("SQLALCHEMY_DATABASE_URI"),
    SQLAlchemy_TRACK_MODIFICATIONS=False,
    TEMPLATES_AUTO_RELOAD=True,
    # add celery configuration
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0'
)

celery_app = create_celery_app(app)  # <-- Rename to 'celery'
register_tasks(celery_app)

db.init_app(app)

# db = SQLAlchemy(app)
migrate = Migrate(app, db)

# This should really be an S3 bucket in production with folder structure and everything.
PROCESSED_FILES_DIR = os.path.join("processed_files")

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY"
)  # Access the secret key from environment variables
CORS(app)

# Instantiate OAuth
oauth = OAuth(app)

oauth.register(
    name="oidc",
    authority=os.getenv("AUTHORITY"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("AUTH_CLIENT_SECRET"),
    server_metadata_url=os.getenv("SERVER_METADATA_URL"),
    client_kwargs={"scope": "email openid"},
)

s3_obj = S3Uploader()
### should update to use user_info instead of user, as user is a param in the oath.oidc.userinfo function!!!
logger.debug("OAuth client registered: {oauth_client}")

current_date = datetime.now()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        if not user:
            return redirect(url_for("index", _external=True, error_msg="Please Login First!"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():  # /metadata_modifier is using index.html and that is dumb.
    user = session.get("user")
    error_msg = request.args.get("error_msg")
    if user:
        logger.debug("User found in session")
        return render_template("login.html", user=user, admin_email=ADMIN_EMAIL)
    else:
        logger.debug("No user found in session")
        return render_template("login.html", user=None, error_msg=error_msg)


@app.route("/login")
def login():
    redirect_uri = os.getenv("CALLBACK_URL")
    logger.debug(f"redirect_uri: {redirect_uri}")
    return oauth.oidc.authorize_redirect(redirect_uri)


@app.route("/logout")
def logout():
    user_info = session.pop("user", None)
    logger.debug(f"User info: {user_info}")
    # Log the session info to the database here
    # Example: log_to_db(user_info)
    session.clear()
    # Redirect to the identity provider's logout endpoint
    redirect_uri = os.getenv("CALLBACK_URL")
    logger.debug(f"In logout. Redirect URI: {redirect_uri}")
    logout_url = os.getenv("LOGOUT_URL")
    return redirect(url_for("index"))


@app.route("/callback")
def callback():
    logger.debug("Callback received")
    try:
        token = oauth.oidc.authorize_access_token()
        logger.debug(f"Token received: {token}")
        user = oauth.oidc.userinfo(token=token)
        logger.debug(f"User info received: {user}")
        session["user"] = user
        provider_type = token.get("userinfo", {}).get("identities", [{}])[0].get("providerType")
        existing_user = user_models.User.query.filter_by(email=user.email).first()
        db_user = db.session.query(user_models.User).filter_by(email=user.email).first()
        if db_user:
           session["profile_image"] = db_user.image_profile
        else:
            session["profile_image"] = None
        if existing_user:
            if not existing_user.stripe_customer_id:
                stripe_manager = StripeSubscriptionManager()
                customer_id = stripe_manager.create_customer(
                    email=user.email,
                    name=user.email.split("@")[0],
                )

                if customer_id:
                    existing_user.stripe_customer_id = customer_id
                else:
                    logger.error("Error creating customer in Stripe during web login after mobile login")
                
            db.session.commit()

            # Update auth_type if it has changed
            if existing_user.auth_type != provider_type:
                existing_user.auth_type = provider_type
                db.session.commit()
            session["profile_image"] = existing_user.image_profile
        else:
            session["profile_image"] = None
            stripe_manager = StripeSubscriptionManager()
            customer_id = stripe_manager.create_customer(
                email=user.email,
                name=user.email.split("@")[0],
            )
            if not customer_id:
                logger.error("Error creating customer in stripe")
            new_user = user_models.User(
                authid=user.sub,
                name=user.email.split("@")[0],
                email=user.email,
                open_id="",
                stripe_customer_id=customer_id if customer_id else None,
                auth_type=provider_type
            )
            db.session.add(new_user)
            db.session.commit()

        return redirect(url_for("metadata_modifier"))
    except Exception as e:
        logger.error(f"User doesn't exist during callback: {e}")
        return redirect(url_for("index"))



@app.route("/metadata_modifier")
@login_required
def metadata_modifier():
    try:
        user = session.get("user")
        profile_image = session.get("profile_image")
        user_email = user.get("email")
        is_subscription=False
        db_user = db.session.query(user_models.User).filter_by(email=user_email).first()

        db_payment = db.session.query(user_models.Payment).filter_by(user_id=db_user.id).all()

        if db_user:
            meta_config = db.session.query(user_models.MetaConfiguration).filter_by(user_id=db_user.id).first()
            meta_info = meta_config.meta_info if meta_config else {}  # Use empty dict if no data found
        else:
            meta_info = {}

        for records in db_payment:
            if records.is_subscription:
                is_subscription=True
                break

        media_rec = db.session.query(user_models.Usercontent).all()

        # Extract all valid image and video URLs
        all_urls = {urlparse(url).path.split("/")[-1] for record in media_rec for url in (record.image_url, record.video_url) if url}

        # Convert the set to a list to maintain unique filenames
        unique_filenames = list(all_urls)
        if isinstance(meta_info, str):
            try:
                meta_info = json.loads(meta_info)
            except json.JSONDecodeError as e:
                print("Error decoding JSON:", e)
        return render_template("index.html", user=user, subscription=is_subscription, profile_image=profile_image, meta_info=meta_info, media_list=unique_filenames,admin_email=ADMIN_EMAIL)
    except Exception as e:
        return render_template("login.html", user=user, subscription=None, profile_image=None, meta_info={}, media_list=[], error_msg = "Something went wrong. Please try again!!!", admin_email=ADMIN_EMAIL)

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    logger.info("Received a file upload request")
    user = session.get("user")
    id = session.get("id")
    profile_image = session.get("profile_image")

    user_email = user.get("email")
    is_subscription=False
    db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
    if db_user:
        meta_config = db.session.query(user_models.MetaConfiguration).filter_by(user_id=db_user.id).first()
        if meta_config:
            if isinstance(meta_config.meta_info, str):
                try:
                    meta_info = json.loads(meta_config.meta_info)
                except json.JSONDecodeError:
                    meta_info = {}
            else:
                meta_info = meta_config.meta_info
        else:
            meta_info = {}

    db_payment = db.session.query(user_models.Payment).filter_by(user_id=db_user.id).all()

    for records in db_payment:
        if records.is_subscription:
            is_subscription=True
            break

    try:
        form_data = request.form.to_dict()

        files = request.files.getlist("files")
        media_list = []

        # Collect all the input parameters into a dictionary.  Are there any that we should require???
        # this should be defined in 1 location and applied to this and index.html without duplication.
        params = OrderedDict(
            {
                "creator_name": form_data.get("creatorName") or None,
                "creator_address": form_data.get("creatorAddress") or None,
                "creator_city": form_data.get("creatorCity") or None,
                "creator_state": form_data.get("creatorState") or None,
                "creator_country": form_data.get("creatorCountry") or None,
                "creator_postal_code": form_data.get("creatorPostalCode") or None,
                "creator_email": form_data.get("creatorEmail") or None,
                "creator_phone": form_data.get("creatorPhone") or None,
                "creator_web_url": form_data.get("creatorWebUrl") or None,
                "creators_jobtitle": form_data.get("creatorJobTitle") or None,
                "credit_line": form_data.get("creditLine") or None,
                "date_created": form_data.get("dateCreated") or None,
                "copyright_notice": form_data.get("copyrightNotice") or None,
                "rights_usage_terms": form_data.get("rightsUsageTerms") or None,
                "description": form_data.get("description") or None,
                "description_writer": form_data.get("descriptionWriter") or None,
                "headline": form_data.get("headline") or None,
                "instructions": form_data.get("instructions") or None,
                "keywords": form_data.get("keywords") or None,
                "title": form_data.get("title") or None,
                "ai_training": form_data.get("aiTraining") or None,
                "ai_generative_training": form_data.get("aiGenerativeTraining") or None,
                "data_mining": form_data.get("dataMining") or None,
                "ai_inference": form_data.get("aiInference") or None,
                "ai_training_constraint_info": form_data.get("aiTrainingConstraintInfo")
                or None,
                "ai_generative_training_constraint_info": form_data.get(
                    "aiGenerativeTrainingConstraintInfo"
                )
                or None,
                "data_mining_constraint_info": form_data.get("dataMiningConstraintInfo")
                or None,
                "ai_inference_constraint_info": form_data.get(
                    "aiInferenceConstraintInfo"
                )
                or None,
                "user_email":user_email,
            }
        )

        logger.debug(f"Params: {params}")

        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']

        for file in files:
            logger.info(f"Processing file: {file.filename}")
            file_data = base64.b64encode(file.read()).decode("utf-8")
            file.seek(0)

            is_video = any(file.filename.lower().endswith(ext) for ext in video_extensions)

            # Check if record already exists for user and filename
            existing_image_status = db.session.query(user_models.ImageStatus).filter_by(
                user_id=db_user.id,
                image_name=file.filename
            ).first()

            if not existing_image_status:
                # Only insert if record doesn't exist
                image_status = user_models.ImageStatus(
                    user_id=db_user.id,
                    image_name=file.filename,
                    image_status="in_progress",
                    upload_date=datetime.utcnow(),
                    image_url=None,  # Will be updated later
                    meta_data=None
                )
                db.session.add(image_status)
                db.session.commit()
            else:
                # Optionally: Update the status back to 'in_progress' if needed
                existing_image_status.image_status = "in_progress"
                existing_image_status.upload_date = datetime.utcnow()
                db.session.commit()

            # Send Celery task
            if is_video:
                task = celery_app.send_task(
                    "celery_worker.video_processing",
                    args=[user_email, file.filename, file_data, params]
                )
            else:
                task = celery_app.send_task(
                    "celery_worker.image_processing",
                    args=[user_email, file.filename, file_data, params]
                )

            
        return render_template("index.html", download_link=True, user=user,subscription=is_subscription,meta_info=meta_info, profile_image=profile_image, media_list=media_list, success_msg="File has been uploaded successfully", admin_email=ADMIN_EMAIL)
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return render_template('index.html', user=user, user_id=user.authid, subscription=is_subscription,meta_info=meta_info, media_list=media_list, profile_image=profile_image, error_msg="Your image has been failed to upload")
    
@app.route("/get_user_files")
@login_required
def get_user_files():
    user_email = session.get("user").get("email")
    db_user = db.session.query(user_models.User).filter_by(email=user_email).first()

    if not db_user:
        return jsonify([])

    # Make sure image_status has a user_id field
    user_files = (
        db.session.query(user_models.ImageStatus.image_name)
        .filter_by(user_id=db_user.id)
        .all()
    )

    file_names = [file.image_name for file in user_files]
    return jsonify(file_names)

@app.route(f"/{PROCESSED_FILES_DIR}/<path:filename>")
@login_required
def serve_processed_file(filename):
    return send_from_directory(PROCESSED_FILES_DIR, filename)


@app.route('/subscription_purchase') 
@login_required
def subscription_purchase():
    error_message = request.args.get("error_msg", None)
    
    user = session.get('user')
    profile_image = session.get("profile_image")
    try:
        # Query all products from the database
        stripe_objects = StripeSubscriptionManager()
        price_list, status_code = stripe_objects.get_price_list()
        if status_code != 200:
            raise Exception("Failed to retrieve price list from Stripe")
        for price in price_list:
            if not price.recurring:
                logger.warning(f"Skipping price {price.id} with no recurring interval")
                continue
            
            products = db.session.query(user_models.Product).filter_by(price_id=price.id).first()
            if not products:
                interval_to_days = {
                        "day": 1,
                        "week": 7,
                        "month": 30,
                        "year": 365
                    }
                time_delta = timedelta(days=interval_to_days.get(price.recurring.interval, 1))

                product_data, status_code = stripe_objects.get_product(price.product)
                if status_code != 200 or not product_data:
                    logger.warning(f"Skipping inactive or non-existent product {price.product}")
                    continue
                
                if price.unit_amount_decimal is None: 
                    price.unit_amount_decimal = 0
                # Check if the product already exists
                existing_product = db.session.query(user_models.Product).filter_by(product_id=price.product).first()
                if existing_product:
                    # Update the existing product
                    existing_product.product_name = product_data.name
                    existing_product.price_id = price.id
                    existing_product.description = product_data.description
                    existing_product.product_price = int(price.unit_amount_decimal) / 100  # Convert cents to dollars
                    existing_product.duration = price.recurring.interval
                    existing_product.update_date = datetime.now(timezone.utc) + time_delta
                    existing_product.is_active = True if int(price.unit_amount_decimal) / 100 > 0 else False  # Update is_active to True if product_price is greater than 0, otherwise False
                    existing_product.price_type = price.type
                    existing_product.billing_scheme = price.billing_scheme
                    db.session.commit()
                else:
                    # Insert a new product
                    new_product = user_models.Product( 
                        product_id=price.product,
                        product_name=product_data.name,
                        price_id=price.id,
                        description=product_data.description,
                        product_price=int(price.unit_amount_decimal) / 100,  # Convert cents to dollars
                        duration=price.recurring.interval,
                        update_date=datetime.now(timezone.utc) + time_delta,
                        price_type = price.type,
                        billing_scheme = price.billing_scheme,
                        is_active = True if int(price.unit_amount_decimal) / 100 > 0 else False  # Set is_active to True if product_price is greater than 0, otherwise False
                    )
                    db.session.add(new_product)
                    db.session.commit()
        # Prepare the product data for the template
        products = user_models.Product.query.filter(user_models.Product.is_active == True).all()  # Retrieve products where is_active is True
        product_list = [
            {
                "product_name": product.product_name,
                "product_price": f"${product.product_price:.2f}/month",  # Format price
                "description": product.description,
                "price_id":product.price_id
            }
            for product in products
        ]

        # Render the template with the product data
        return render_template('purchase.html', products=product_list if product_list else [], user=user,  profile_image=profile_image, error_msg=error_message, admin_email=ADMIN_EMAIL)
    
    except Exception as e:
        # Handle any errors that occur
        return jsonify({"error": str(e)}), 500


@app.route("/blog")
def blog():
        return redirect("https://blog.longtailedleopard.com/")


@app.route("/contact")
def contact():
    user = session.get("user")
    success_msg = request.args.get("success_msg")
    profile_image = session.get("profile_image")
    return render_template("contact.html", user=user, profile_image=profile_image, success_msg=success_msg, admin_email=ADMIN_EMAIL)


@app.route("/subscription")
def subscription():
    try:
        user = session.get("user")
        error_message = request.args.get("error_msg", None)
        success_msg = request.args.get("success_msg", None)

        profile_image = session.get("profile_image")

        if not user or "email" not in user:
            logger.warning("Unauthorized access attempt to /subscription")
            error_message = "Unauthorized access"  # Assign the error message
            return render_template(
                "subscription.html", error_msg=error_message
            )  # Pass it to the template
        user_email = user["email"]

        payments = (
            user_models.Payment.query.join(
                user_models.User, user_models.Payment.user_id == user_models.User.id
            )
            .filter(user_models.User.email == user_email)
            .all()
        )
        # Prepare payment data
        payment_list = [
            {
                "payment_amount": f"${payment.payment_amount:.2f}",
                "product_name": (
                    payment.product.product_name if payment.product else "N/A"
                ),
                "payment_date": payment.payment_date.strftime("%Y-%m-%d"),
                "payment_status": payment.payment_status,
                "subscription_id": payment.subscription_id,
                "payment_id": payment.payment_id,
                "refund_status": payment.refund_status,
            }
            for payment in payments
        ]
        if error_message:
            return render_template("subscription.html", payments=payment_list, user=user, profile_image=profile_image, error_msg=error_message, admin_email=ADMIN_EMAIL)
        elif success_msg:
            return render_template("subscription.html", payments=payment_list, user=user, profile_image=profile_image, success_msg=success_msg, admin_email=ADMIN_EMAIL)
        logger.info(f"Retrieved {len(payment_list)} payments for user: {user_email}")
        return render_template("subscription.html", payments=payment_list, user=user, profile_image=profile_image, admin_email=ADMIN_EMAIL)

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return render_template(
            "subscription.html", error_msg=str(e)
        )  # Pass it to the template
 

@app.route("/checkout", methods=["POST"])
@login_required
def create_session():
    try:

        user = session.get("user")
        user_email = user.get('email')

        user_data = db.session.query(user_models.User).filter_by(email=user_email).first()
        if not user_data:
            raise Exception("User not found in the database.")
        try:
            stripe_manager = StripeSubscriptionManager()
            if not user_data.stripe_customer_id:
                customer_id = stripe_manager.create_customer(email=user_data.email, name=user_data.name)
                user_data.stripe_customer_id = customer_id
                db.session.commit()

            price_id = request.form.get("price_id")
            stripe_session = stripe_manager.create_checkout_session(
                customer_id=user_data.stripe_customer_id,
                price_id=price_id
            )
            return redirect(stripe_session.url)
        except Exception as e:
                customer_id = stripe_manager.create_customer(email=user_data.email, name=user_data.name)
                user_data.stripe_customer_id = customer_id
                db.session.commit()

                price_id = request.form.get("price_id")
                stripe_session = stripe_manager.create_checkout_session(
                    customer_id=user_data.stripe_customer_id,
                    price_id=price_id
                )
                return redirect(stripe_session.url)

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return render_template(
            "purchase.html", error_msg=str(e)
        )


@app.route("/success", methods=["GET"])
def stripe_callback():
    try:
        session_id = request.args.get("session_id")
        if not session_id:
            raise ValueError("Session ID is missing from the request.")

        # Initialize StripeSubscriptionManager
        stripe_manager = StripeSubscriptionManager()

        # Retrieve the checkout session details
        stripe_session = stripe_manager.retrieve_checkout_session(session_id)
        if not stripe_session:
            raise ValueError("Error retrieving Stripe session.")
        
        sub_id = stripe_session.get("subscription")
        
        if stripe_session.payment_status == "paid":
            customer_id = (
                db.session.query(user_models.User)
                .filter_by(stripe_customer_id=stripe_session.customer)
                .first()
            )
            logger.info(f"Payment successful for session: {stripe_session.id}")
            invoice_id = stripe_session.invoice
            invoice = stripe_manager.get_invoice(invoice_id)

            subscription = stripe.Subscription.retrieve(sub_id)
            
            tax_rates = subscription.default_tax_rates  


            payment_intent_id = invoice.get("payment_intent")
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            payment_id = payment_intent.get("id")

            payment_method = payment_intent.get("payment_method")

            invoice_date = utils.convert_unix_to_utc(invoice.period_start)
            complete_date = utils.convert_unix_to_utc(invoice.period_end)
            product_id = invoice.lines.data[0].plan.product
            product_id = (
                db.session.query(user_models.Product)
                .filter_by(product_id=product_id)
                .first()
            )

            # TODO: Save the invoice to the database
            db_invoice = (
                db.session.query(user_models.Invoice)
                .filter_by(invoice_id=invoice_id)
                .first()
            )
            if not db_invoice:
                db_invoice = user_models.Invoice(
                    invoice_id=invoice_id,
                    auth_id=customer_id.id,
                    invoice_date=invoice_date,
                    complete_date=complete_date,
                    total_amount=invoice.total / 100,
                )
                db.session.add(db_invoice)
                db.session.commit()
            # TODO: Save the invoice details to the database
            db_invoice_details = user_models.InvoiceDetails(
                invoice_id=db_invoice.id,
                product_id=product_id.id,
                currency=invoice.currency,
            )
            db.session.add(db_invoice_details)

            db_payment_status = user_models.PaymentStatus(
                status_name=stripe_session.status, subscription_id=sub_id
            )
            db.session.add(db_payment_status)
            db.session.commit()

            db_payment_method = user_models.PaymentMethod(
                method_name=stripe_session.payment_method_types[0],
                method_id=payment_method,
            )
            db.session.add(db_payment_method)
            db.session.commit()

            db_payment = user_models.Payment(
                user_id=customer_id.id,
                product_id=product_id.id,
                invoice_id=db_invoice.id,
                payment_status=stripe_session.status,
                payment_id=payment_id,
                payment_date=datetime.utcnow(),
                payment_amount=invoice.total / 100,
                method_id=db_payment_method.id,
                status_id=db_payment_status.id,
                subscription_id=sub_id,
                is_subscription=True
            )
            db.session.add(db_payment)
            db.session.commit()

        # Pass session data to the HTML template
        return render_template("success.html", stripe_session=stripe_session)
    except Exception as e:
        logger.debug(f"Error retrieving Stripe session: {e}")
        return render_template("error.html", error_message=str(e))


@app.route("/cancelsubscription", methods=["POST"])
def subscription_cancel():
    try:
        body ="Your ongoing Subscription has been canceled."
        stripe_manager = StripeSubscriptionManager()
        subscription_id = request.form.get("subscription_id")
        description = request.form.get("description")
        stripe_session = stripe_manager.cancel_subscription(subscription_id)
        user = session.get("user")
        user_email = user.get("email")
        payment_record = (
            db.session.query(user_models.Payment)
            .filter_by(subscription_id=subscription_id)
            .first()
        )
        payment_date = payment_record.payment_date
        payment_id = payment_record.payment_id
        days_difference = (current_date - payment_date).days

        paymentstatus = user_models.PaymentStatus(
            status_name=stripe_session.status,
            description=description,
            subscription_id=subscription_id,
        )
        db.session.add(paymentstatus)
        db.session.commit()
        if payment_record:
            payment_record.payment_status = stripe_session.status
            payment_record.is_subscription = False
            db.session.commit()
        else:
            logger.debug("No payment record found for the provided subscription ID")

        if days_difference <= 7:
            body = 'Your ongoing Subscription has been canceled. Refund Initiated'
            if stripe_manager.refund_request(payment_id, user_email):
                # return redirect(url_for("subscription"))
                pass
            else:
                return redirect(url_for("subscription", error_msg='Stripe session not found'))
        cancel_email = send_email(body, email=user_email)
        return redirect(url_for("subscription", success_msg="Your Subscription has been canceled successfully."))
        
    except Exception as e:
        return render_template('subscription.html', error_msg=str(e))


@app.route("/requestrefund", methods=["POST"])
def refund_create():
    try:
        stripe_manager = StripeSubscriptionManager()
        intent_id = request.form.get("payment_id")
        subscription_id = request.form.get("refund_subscription_id")

        user = session.get("user")
        user_email = user.get("email")

        payment_record = (
            db.session.query(user_models.Payment)
            .filter_by(subscription_id=subscription_id)
            .first()
        )
        payment_id = payment_record.payment_id
        days_difference = (current_date - payment_record.payment_date).days

        if days_difference > 7:
            body = f"The user with the mail id: {user_email} has been requested for the refund. Please accept/reject it."
            mail_send = send_email(body)
            db_payment = (
                db.session.query(user_models.Payment)
                .filter_by(payment_id=intent_id)
                .first()
            )

            if db_payment:
                # Update the refund_status
                db_payment.refund_status = 'Pending'

            db_refund = (
                db.session.query(user_models.PaymentRefund).filter_by(inten_id=intent_id).first()
            )

            user = db.session.query(user_models.User).filter_by(email=user_email).first()

            if db_refund:
                db_refund.refund_status = 'Pending'

            else:
                # If no record exists, create a new one
                db_refund = user_models.PaymentRefund(
                    inten_id=intent_id, refund_status='Pending',user_id=user.id,refund_date=datetime.utcnow()
                )
                db.session.add(db_refund)

            db.session.commit()
        else:
            stripe_manager.refund_request(payment_id, user_email)

            ## Cancel Process Started ##
            stripe_session = stripe_manager.cancel_subscription(subscription_id)
            payment_record = (
                db.session.query(user_models.Payment)
                .filter_by(subscription_id=subscription_id)
                .first()
            )
            payment_date = payment_record.payment_date
            payment_id = payment_record.payment_id
            days_difference = (current_date - payment_date).days

            paymentstatus = user_models.PaymentStatus(
                status_name=stripe_session.status,
                description="Due to Payment Refunded",
                subscription_id=subscription_id,
            )
            db.session.add(paymentstatus)
            db.session.commit()
            if payment_record:
                payment_record.payment_status = stripe_session.status
                payment_record.is_subscription=False
                db.session.commit()
            else:
                logger.debug("No payment record found for the provided subscription ID")

        return redirect(url_for("subscription", success_msg="Your Request for refund has been sent."))
        
    except Exception as e:
        return redirect(url_for("subscription", error_msg=str(e)))
    
@app.route("/admindashboard", methods=["GET"])
@login_required
def admin_dashboard():
    try:
        error_message = request.args.get("error_msg", None)
        success_msg = request.args.get("success_msg", None)
        user = session.get("user")
        user_email = user.get("email")
        profile_image = session.get("profile_image")

        if user_email != ADMIN_EMAIL:
            return render_template('index.html', error_msg='You are not allowed to access this.')
        RefundAlias = aliased(user_models.PaymentRefund)

        payments = (
        user_models.Payment.query
        .join(user_models.User, user_models.Payment.user_id == user_models.User.id)
        .outerjoin(RefundAlias, user_models.Payment.payment_id == RefundAlias.inten_id)
        .filter(user_models.Payment.refund_status == "Pending")
        .add_columns(RefundAlias.refund_date)
        .all()
        ) 

        payment_list = [
            {
                "payment_amount": f"${payment.payment_amount:.2f}",
                "product_name": payment.product.product_name if payment.product else "N/A",
                "payment_date": payment.payment_date.strftime("%Y-%m-%d"),
                "payment_status": payment.payment_status,
                "subscription_id": payment.subscription_id,
                "payment_id": payment.payment_id,
                "refund_status": payment.refund_status,
                "email": payment.user.email,
                "refund_date": refund_date if refund_date else None,  # Extract refund_date correctly
            }
            for payment, refund_date in payments  # Correct unpacking of tuple
        ]

        if error_message:
            return render_template("admin.html", payments=payment_list, user=user, profile_image=profile_image, error_msg=error_message, admin_email=ADMIN_EMAIL)
        elif success_msg:
            return render_template("admin.html", payments=payment_list, user=user, profile_image=profile_image, success_msg=success_msg, admin_email=ADMIN_EMAIL)
        
        return render_template('admin.html', payments=payment_list, user=user, profile_image=profile_image, admin_email=ADMIN_EMAIL)
    except Exception as e:
        return render_template('admin.html', payments=[], user=user, admin_email=ADMIN_EMAIL, error_msg="Something went wrong. Please try again.")


@app.route("/approve_refund", methods=["POST"])
def approve_refund():
    try:

        stripe_manager = StripeSubscriptionManager()
        subscription_id = request.form.get("subscription_id")
        user = session.get("user")
        user_email = user.get("email")

        body = f"Your request for refund has been successfully approved."
        receive_email = send_email(body,email=user_email)

        payment_record = (
                db.session.query(user_models.Payment)
                .filter_by(subscription_id=subscription_id)
                .first()
            )
        
        payment_id = payment_record.payment_id

        stripe_manager.refund_request(payment_id, user_email)

        if payment_record.payment_status != "canceled":
            stripe_session = stripe_manager.cancel_subscription(subscription_id)
        
            paymentstatus = user_models.PaymentStatus(
                status_name=stripe_session.status,
                description="Due to Payment Refunded.",
                subscription_id=subscription_id,
            )
            db.session.add(paymentstatus)

            db.session.commit()

            if payment_record:
                payment_record.payment_status = stripe_session.status
                payment_record.is_subscription = False
                db.session.commit()
            else:
                logger.debug("No payment record found for the provided subscription ID") 

        return redirect(url_for("admin_dashboard", success_msg="Successfully Approved."))
    
    except Exception as e:
        return redirect(url_for("admin_dashboard", error_msg=str(e)))


@app.route("/reject_refund", methods=["POST"])
def reject_refund():
    try:
        user = session.get("user")
        user_email = user.get("email")
        subscription_id = request.form.get("subscription_id")
        intent_id = request.form.get("payment_id")

        body = f"Your request for refund has been rejected. Please Try Again!!"
        reject_email = send_email(body, email=user_email)
        
        payment = user_models.Payment.query.filter_by(subscription_id=subscription_id).first()

        refund = user_models.PaymentRefund.query.filter_by(inten_id=intent_id).first()

        if payment:
            payment.refund_status = "Rejected"

        if refund:
            refund.refund_status = "Rejected"

        db.session.commit() 
        return redirect(url_for("admin_dashboard", success_msg="Successfully Rejected."))  
    except Exception as e:
        return redirect(url_for("admin_dashboard", error_msg=str(e)))
    
@login_required
@app.route("/configuration_details", methods=["POST", "GET"])
def configuration():
    user = session.get("user")
    user_email = user.get("email")
    profile_image = session.get("profile_image")
    # Fetch user data
    user_data = db.session.query(user_models.User).filter_by(email=user_email).first()
    existing_meta = None

    if user_data:
        existing_meta = db.session.query(user_models.MetaConfiguration).filter_by(user_id=user_data.id).first()

    if request.method == 'GET':
        if existing_meta and existing_meta.meta_info:
            try:
                meta_info = json.loads(existing_meta.meta_info) if isinstance(existing_meta.meta_info, str) else existing_meta.meta_info
            except json.JSONDecodeError:
                meta_info = {}
        else:
            meta_info = {}

        return render_template("configuration.html", user=user, meta_info=meta_info, profile_image=profile_image, admin_email=ADMIN_EMAIL)

    else:
        form_data = request.form.to_dict()
        params = OrderedDict(
            {
                "creator_name": form_data.get("creatorName") or None,
                "creator_address": form_data.get("creatorAddress") or None,
                "creator_city": form_data.get("creatorCity") or None,
                "creator_state": form_data.get("creatorState") or None,
                "creator_country": form_data.get("creatorCountry") or None,
                "creator_postal_code": form_data.get("creatorPostalCode") or None,
                "creator_email": form_data.get("creatorEmail") or None,
                "creator_phone": form_data.get("creatorPhone") or None,
                "creator_web_url": form_data.get("creatorWebUrl") or None,
                "creators_jobtitle": form_data.get("creatorJobTitle") or None,
                "credit_line": form_data.get("creditLine") or None,
                "date_created": form_data.get("dateCreated") or None,
                "copyright_notice": form_data.get("copyrightNotice") or None,
                "rights_usage_terms": form_data.get("rightsUsageTerms") or None,
                "description": form_data.get("description") or None,
                "description_writer": form_data.get("descriptionWriter") or None,
                "headline": form_data.get("headline") or None,
                "instructions": form_data.get("instructions") or None,
                "keywords": form_data.get("keywords") or None,
                "title": form_data.get("title") or None,
                "ai_training": form_data.get("aiTraining") or None,
                "ai_generative_training": form_data.get("aiGenerativeTraining") or None,
                "data_mining": form_data.get("dataMining") or None,
                "ai_inference": form_data.get("aiInference") or None,
                "ai_training_constraint_info": form_data.get("aiTrainingConstraintInfo") or None,
                "ai_generative_training_constraint_info": form_data.get("aiGenerativeTrainingConstraintInfo") or None,
                "data_mining_constraint_info": form_data.get("dataMiningConstraintInfo") or None,
                "ai_inference_constraint_info": form_data.get("aiInferenceConstraintInfo") or None,
            }
        )

        if existing_meta:
            # Update existing record
            existing_meta.meta_info = json.dumps(params)
        else:
            # Create new record
            new_meta = user_models.MetaConfiguration(user_id=user_data.id, meta_info=json.dumps(params))
            db.session.add(new_meta)

        # Commit changes
        db.session.commit()

        return render_template("configuration.html", user=user, meta_info=params, profile_image=profile_image, success_msg="Your data has been saved successfully.", admin_email=ADMIN_EMAIL)

@login_required
@app.route("/user_gallery", methods=["GET"])
def user_gallery():
    try:
        user = session.get("user")
        success_msg = request.args.get('success_msg')
        profile_image = session.get("profile_image")

        if user is None:
            return render_template("login.html", user=None, error_msg="Please Login First")

        user_email = user.get("email")
        db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
        user_contents = user_models.Usercontent.query.filter_by(user_id=db_user.id).all()

        s3_uploader = S3Uploader()
        content_data = []

        for content in user_contents:
            file_url = content.image_url or content.video_url
            if not file_url:
                continue

            parsed_url = urlparse(file_url)
            s3_key = unquote(parsed_url.path.lstrip('/'))
            original_filename = os.path.basename(s3_key)

            download_url = s3_uploader.generate_download_url(s3_key, original_filename)

            content_data.append({
                "content_url": file_url,
                "download_url": download_url
            })

        return render_template(
            "gallery.html",
            user=user,
            user_contents=content_data,
            success_msg=success_msg,
            profile_image=profile_image,
            admin_email=ADMIN_EMAIL
        )

    except Exception as e:
        return render_template(
            "gallery.html",
            user=user,
            user_contents=[],
            profile_image=profile_image,
            success_msg=success_msg,
            admin_email=ADMIN_EMAIL,
            error_msg=str(e)
        )
    
@app.route("/image_hub", methods=["GET"])
def image_hub():
    try:
        user = session.get("user")
        profile_image = session.get("profile_image")
        search_query = request.args.get("search", "").strip().lower()
        sort_order = request.args.get("sort", "name_asc")
        content_obj = user_models.Usercontent.query.all()

        s3_uploader = S3Uploader()
        content_data = {}

        for content in content_obj:
            user_email = content.user.email
            file_url = content.image_url if content.image_url else content.video_url
            if not file_url:
                continue

            parsed_url = urlparse(file_url)
            s3_key = unquote(parsed_url.path.lstrip('/'))
            filename = os.path.basename(s3_key)

            if search_query:
                if (
                    search_query not in user_email.lower() and
                    search_query not in file_url.lower() and
                    search_query not in filename
                ):
                    continue

            # Generate presigned download URL
            download_url = s3_uploader.generate_download_url(s3_key, filename)

            if user_email not in content_data:
                content_data[user_email] = {"imageurl": []}

            content_data[user_email]["imageurl"].append({
                "original_url": file_url,
                "filename": filename,
                "download_url": download_url
            })

        for user_email in content_data:
            content_data[user_email]["imageurl"].sort(
                key=lambda x: x["filename"],
                reverse=(sort_order == "name_desc")
            )

        return render_template(
            "public.html",
            user=user,
            content_obj=content_data,
            profile_image=profile_image,
            admin_email=ADMIN_EMAIL
        )

    except Exception as e:
        return render_template(
            "public.html",
            user=user,
            content_obj={},
            admin_email=ADMIN_EMAIL,
            error_msg="Something went wrong. Please try again."
        )

@app.route("/image_status", methods=["GET"])
def image_status():
    try:
        user = session.get("user")
        profile_image = session.get("profile_image")
        if user is None:
            return render_template("login.html", user=None, error_msg="Please Login First")
        user_email = user.get("email")
        error_msg = request.args.get("error_msg")
        success_msg = request.args.get("success_msg")
        user_record = user_models.User.query.filter_by(email=user_email).first()
        image_list = user_models.ImageStatus.query.filter_by(user_id=user_record.id).all()

        image_row = [
            {
                "image_id": image.id,
                "image_name": image.image_name,
                "image_status": image.image_status,
                "upload_date": image.upload_date,
                "image_url": image.image_url
            }
            for image in image_list
        ]    

        return render_template("imagestatus.html", user=user, image_row=image_row, image_list=image_list, profile_image=profile_image, error_msg=error_msg, success_msg=success_msg, admin_email=ADMIN_EMAIL)
    except Exception as e:
        return render_template("imagestatus.html", user=user, image_row=[], image_list=[], error_msg="Something went wrong. Please try again!!!", profile_image=None, success_msg=None, admin_email=ADMIN_EMAIL)

@app.route("/reload", methods=["POST"])
def img_reload():
    try:
        image_id = request.form.get("image_id")
        user = session.get('user')
        user_email = user.get('email')
        image_record = user_models.ImageStatus.query.filter_by(id=image_id).first()  # Add parentheses
        video_url=None
        image_url=None

        if image_record:
            img_name = image_record.image_name,
            img_url = image_record.image_url,
            img_meta = image_record.meta_data
            img_meta["record_id"]=image_record.id
            response = requests.get(img_url[0], stream=True)
            # image_file = io.BytesIO(response.content)
            image_io = io.BytesIO(response.content)
            image_io.seek(0) 
            file_storage = FileStorage(
                stream=image_io,
                filename=img_url[0].split("/")[-1],  # Extract filename from URL
                content_type=response.headers.get("Content-Type", "image/jpeg")
            ) 


            filename = img_url[0].split("/")[-1]

            # Mimic request.files format (a list of FileStorage objects)
            file_list = [file_storage]
            db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
            # image_file.name = img_url.split("/")[-1] 
            download_link , image_name = asyncio.run(c2pa_utils.process_file(file_storage, **img_meta))
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            if any(download_link.lower().endswith(ext) for ext in video_extensions):
                video_url = s3_obj.upload_video(local_video_path=download_link, user_email=user_email,original_filename=filename)
            else:
                image_url = s3_obj.upload_image(local_image_path=download_link, user_email=user_email,original_filename=filename) 
            user_obj = db.session.query(user_models.User).filter_by(email=user_email).first()
        
            image_record.image_name=filename
            image_record.image_status="succeeded"
            image_record.image_url=video_url if video_url else image_url
            db.session.commit()
            if video_url:
                new_product = user_models.Usercontent(user_id=user_obj.id,video_url=video_url)
            else:
                new_product = user_models.Usercontent(user_id=user_obj.id,image_url=image_url)
            db.session.add(new_product)
            db.session.commit()
            if os.path.exists(download_link):
                os.remove(download_link)
            if os.path.exists(f"processed_files/{image_name}"):
                os.remove(f"processed_files/{image_name}")
            logger.info(f"Download link: {download_link}")
            logger.info(f"Download link: {download_link}")
            return redirect(url_for("image_status", success_msg="Your file has been reloaded"))
        else:
            print("No image record found for the given ID")

        return "Reloaded"
    except Exception as e:
        return redirect(url_for("image_status", error_msg="Reload Unsuccessful! Please try again.."))
    
# Set upload folder
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def upload_profile():
    try:
        user = session.get("user", {})
        user_email = user.get("email")
        error_msg = request.args.get("error_msg")
        profile_image = session.get("profile_image")
        
        db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
        # if db_user and db_user.image_profile:
        #         profile_image = db_user.image_profile  

        meta_info_data = {}
        if db_user:
            meta_config = db.session.query(user_models.MetaConfiguration).filter_by(user_id=db_user.id).first()
            if meta_config:
                meta_info_data = meta_config.meta_info  

            # Count images and videos
            image_count = db.session.query(user_models.Usercontent).filter(
                user_models.Usercontent.user_id == db_user.id, user_models.Usercontent.image_url.isnot(None)
            ).count()

            video_count = db.session.query(user_models.Usercontent).filter(
                user_models.Usercontent.user_id == db_user.id, user_models.Usercontent.video_url.isnot(None)
            ).count()
        else:
            image_count = 0
            video_count = 0

        if request.method == "POST":
                if "file" not in request.files:
                    return "No file part", 400
                file = request.files["file"]
                
                if file.filename == "":
                    return "No selected file", 400
                
                if file:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                
                    s3_url = s3_obj.upload_image(local_image_path=file_path,user_email=user_email,original_filename=filename)

                    db_user = db.session.query(user_models.User).filter_by(email=user_email).first()
                    if db_user:
                        db_user.image_profile = s3_url
                        db.session.commit()
                    session["profile_image"] = s3_url

                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(f"uploads/{filename}"):
                        os.remove(f"uploads/{filename}")

                if db_user and db_user.image_profile:
                    profile_image = db_user.image_profile  
                return render_template("profile.html", user=user, profile_image=profile_image, meta_info=meta_info_data, image_count=image_count,
                    video_count=video_count, admin_email=ADMIN_EMAIL, error_msg=error_msg, success_msg="Profile pic has been uploaded successfully.")

        return render_template("profile.html", user=user, profile_image=profile_image, meta_info=meta_info_data, image_count=image_count,
            video_count=video_count, admin_email=ADMIN_EMAIL, error_msg=error_msg)
    except Exception as e:
        return render_template("profile.html", user=user, meta_info={}, error_msg="Something went wrong. Please try again!!!")

@app.route("/delete_account", methods=["POST"])
def delete_profile():
    try:
        user = session.get('user')
        user_sub = user.get('sub')

        user_rec = db.session.query(user_models.User).filter_by(authid=user_sub).first()

        user_id = user_rec.id  

        db.session.query(user_models.MetaConfiguration).filter_by(user_id=user_id).delete(synchronize_session=False)

        db.session.query(user_models.Usercontent).filter_by(user_id=user_id).delete(synchronize_session=False)


        db.session.query(user_models.InvoiceDetails).filter(
                user_models.InvoiceDetails.invoice_id.in_(
                    db.session.query(user_models.Invoice.id).filter_by(auth_id=user_id)
                )
            ).delete(synchronize_session=False)
        
        db.session.query(user_models.Payment).filter(
                user_models.Payment.invoice_id.in_(
                    db.session.query(user_models.Invoice.id).filter_by(auth_id=user_id)
                )
            ).delete(synchronize_session=False)

        db.session.query(user_models.Invoice).filter_by(auth_id=user_id).delete(synchronize_session=False)
        db.session.query(user_models.ImageStatus).filter_by(user_id=user_id).delete()
        db.session.query(user_models.PaymentRefund).filter_by(user_id=user_id).delete()

        db.session.query(user_models.User).filter_by(id=user_id).delete()

        db.session.commit()

        session.clear()

        return render_template('login.html', user=None, success_msg="Your account has been deleted sucessfully.")
    except Exception as e:
        return redirect(url_for("upload_profile", error_msg="Something went wrong. Please try Again."))
    
@app.route("/delete_image", methods=["POST"])
def delete_image():
    user = session.get('user')
    user_email = user.get("email")
    db_user = db.session.query(user_models.User).filter_by(email=user_email).first()

    user_id = db_user.id 

    file_url = request.form.get('file_url')

    content = user_models.Usercontent.query.filter_by(user_id=user_id).filter(
        (user_models.Usercontent.image_url == file_url) | 
        (user_models.Usercontent.video_url == file_url)
    ).first()
    if content:
        db.session.delete(content)

    status_entry = user_models.ImageStatus.query.filter_by(user_id=user_id, image_url=file_url).first()
    if status_entry:
        db.session.delete(status_entry)
        
    db.session.commit()

    return redirect(url_for("user_gallery", success_msg="Your image has been deleted sucessfully."))


@app.route("/get_cr_metadata", methods=["GET"])
def get_cr_metadata():
    try:
        # Session check
        user = session.get('user')
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

        # Get file_url from query param
        file_url = request.args.get('file_url')
        if not file_url:
            return jsonify({"message": "Missing 'file_url' parameter."}), 400

        # Extract filename from S3 URL
        parsed_url = urlparse(file_url)
        image_name = unquote(parsed_url.path.split("/")[-1])

        # Look for the media content (no user_id filter here)
        image_content = user_models.Usercontent.query.filter(
            or_(
                user_models.Usercontent.image_url.ilike(f"%{image_name}"),
                user_models.Usercontent.video_url.ilike(f"%{image_name}")
            )
        ).first()

        if not image_content:
            return jsonify({"message": "Media not found."}), 404

        if not image_content.meta_data:
            return jsonify({"message": "CR metadata not found."}), 404

        return jsonify({
            "message": "CR metadata fetched successfully.",
            "data": json.loads(image_content.meta_data)
        })

    except Exception as e:
        print("Exception occurred:", str(e))
        return jsonify({"message": "Internal server error.", "error": str(e)}), 500


@app.route("/contact_us", methods=["POST"])
def contact_us():
    name = request.form.get("name")
    user_email = request.form.get("email")
    subject_from_user = request.form.get("subject")  # Rename for clarity
    message = request.form.get("message")

    body = f"The user with the name:{name} and email:{user_email} has the following query.Here is the query:{message}."
    send_email(body, subject=subject_from_user)

    return redirect(url_for("contact", success_msg="Your query has been sent successfully."))

@app.route("/privacy_policy")
def privacy_policy():
    user = session.get('user')
    return render_template("privacy_policy.html", user=user)

@app.route("/terms_conditions")
def terms_conditions():
    user = session.get('user')
    return render_template("terms_conditions.html", user=user)


@app.route("/our_services")
def our_services():
    return render_template("services.html")

# Start Task Endpoint
@app.route('/start-task/<int:seconds>', methods=['GET'])
def start_task(seconds):
    """Start a background task."""
    task = celery_app.send_task('celery_worker.long_running_task', args=[seconds])
    return jsonify({'task_id': task.id, 'status': 'STARTED'})


# Task Status Endpoint
@app.route('/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get task status from the database."""
    task = user_models.TaskLog.query.filter_by(task_id=task_id).first()
    if task:
        return jsonify({
            'task_id': task.task_id,
            'status': task.status,
            'result': task.result,
            'error_message': task.error_message
        })
    return jsonify({'message': 'Task not found'}), 404

@app.route("/healthz")
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)

import os
import json
from datetime import datetime
from c2pa import sign_ps256, create_signer, SigningAlg, Builder
import io
import logging
import asyncio
import aiofiles
from collections import OrderedDict
import boto3
from botocore.exceptions import ClientError
from hashlib import sha256
from dotenv import load_dotenv
from apps.organization.helpers.s3_helpers import S3Uploader
from dotenv import load_dotenv
from apps.organization.models import OrgUser, ImageStatus
from asgiref.sync import sync_to_async
# from helpers.s3_helpers import S3Uploader

logger = logging.getLogger(__name__)

s3_obj = S3Uploader()

load_dotenv()

env = os.getenv('ENV', 'dev')
logger.info(f"Loaded ENV: {env}")

# env = os.getenv('ENV')
# if env == 'prod':
#     load_dotenv('production.env')
# else:
#     load_dotenv('dev.env')

# Directory where the test public and private keys are stored for dev & testing
data_dir = os.path.join("tests", "fixtures")

#Directory where the certs are stored for production
certs_dir = os.path.join("certs")

kms_key_id = "mrk-b368f1fffffd450da98a983f68ea9bf8"

if env == 'prod':
    kms = boto3.client('kms', region_name='us-west-2')

### Logging Init, be good to make fanicer later... 
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - Line: %(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("c2pa_utils.log"),
        logging.StreamHandler()
    ]
)

### File Signing Functions
###### Need to a dev and production version of this.  Specifically, need AWS connect to KMS to get the private key for a production environment.
# Function to get the signing key

### Signing Function for dev
def dev_private_sign(data: bytes) -> bytes:
    private_key = os.path.join(data_dir, "ps256.pem")
    return sign_ps256(data, private_key)

### Signing Function for prod
def kms_sign(data: bytes) -> bytes:
    hashed_data = sha256(data).digest()
    return kms.sign(KeyId=kms_key_id, Message=hashed_data, MessageType="DIGEST", SigningAlgorithm="RSASSA_PSS_SHA_256")["Signature"]

# Function to get the certificate
def get_certs():
    # Pulls in the public key for signing the manifest
    try:
        if env == 'prod':
            # Read the production certs from the certs directory
            cert_path = os.path.join(certs_dir, "long_tailed_leopard_llc.crt")
        else:
            # Use local test certs for development, assume dev environment
            cert_path = os.path.join(data_dir, "ps256.pub")

        with open(cert_path, "rb") as cert_file:
            certs = cert_file.read()
        
        logging.debug(f"Successfully read certs from {cert_path}")
        return certs
    
    except Exception as e:
        logging.error(f"Error reading certs: {e}")
        return None

async def sign_manifest(builder, signer, read_path, save_path):
    logger.info("Signing manifest and adding it to the file")

    logger.debug(f"signer: {signer}, read_path: {read_path}, save_path: {save_path}")
    logger.debug(f"signer type: {type(signer)}, read_path type: {type(read_path)}, save_path type: {type(save_path)}")

    # Check if read_path exists
    if not os.path.exists(read_path):
        logger.error(f"Read path does not exist: {read_path}")
        return

    try:
        # Ensure the file in read_path has fully uploaded
        async with aiofiles.open(read_path, 'rb') as f:
            content = await f.read()
            if not content:
                logger.error(f"File {read_path} is empty or not fully uploaded.")
                return
            logger.debug(f"File {read_path} has been fully uploaded with size: {len(content)} bytes")
    except Exception as e:
        logger.error(f"Error reading file: {e}")

    try:
        # Additional logging before calling sign_file
        logger.debug(f"Calling sign_file with signer: {signer}, read_path: {read_path}, save_path: {save_path}")
        logger.debug(f"signer type: {type(signer)}, read_path type: {type(read_path)}, save_path type: {type(save_path)}")

        try:
            signed_file = builder.sign_file(signer, read_path, save_path)
            logger.debug(f"builder.sign_file successful")
        except Exception as e:
            logger.error(f"Error during builder.sign_file call: {e}")
            raise

        # Asynchronous check if the file exists and its content
        async with aiofiles.open(save_path, 'rb') as f:
            signed_content = await f.read()
            if not signed_content:
                logger.error(f"File {save_path} is empty after signing.")
                return
            logger.debug(f"File {save_path} has been signed with size: {len(signed_content)} bytes")

        # Return the signed file path
        return save_path
    except FileNotFoundError as fnf_error:
        logger.error(f"FileNotFoundError: {fnf_error.name} - {fnf_error.strerror}")
    except Exception as e:
        logger.error(f"Error signing manifest: {e}")
        logger.error(f"Exception details: {type(e).__name__}, {e.args}")


    ###### End of Adding Signed C2PA Manifest to the file
    logger.info(f"File saved to {save_path}")

    # For now, we'll just return the path where the file was saved
    return save_path

async def process_file(file, **kwargs):
    copy_kwargs = kwargs.copy()  
    """
    Process the file with the given metadata.

    Parameters:
    - file: The file to process.

    - kwargs: Additional metadata fields as keyword arguments.
    """

    # Compile the C2PA manifest
    #
    # For the training-mining, you can find the example here: https://creator-assertions.github.io/training-and-data-mining/1.0/#_assertion_definition
    # Probably want to implement:
    #
    #   "use": "constrained",
	#	"constraint_info": "may only be mined on days whose names end in 'y'"
    #
    # For the metadata, you can find the example here: https://creator-assertions.github.io/metadata/1.0/#_assertion_definition
    try:
        try:
            logger.debug(f"Received metadata entries: {kwargs}")

            # Extract the AI control parameters
            user_email = kwargs.get('user_email', None)
            data_mining = kwargs.pop('data_mining', None)
            ai_inference = kwargs.pop('ai_inference', None)
            ai_training = kwargs.pop('ai_training', None)
            ai_generative_training = kwargs.pop('ai_generative_training', None)

            # Extract the constraint_info fields
            data_mining_constraint_info = kwargs.pop('data_mining_constraint_info', None)
            ai_inference_constraint_info = kwargs.pop('ai_inference_constraint_info', None)
            ai_training_constraint_info = kwargs.pop('ai_training_constraint_info', None)
            ai_generative_training_constraint_info = kwargs.pop('ai_generative_training_constraint_info', None)

            # need to add a text field in the constrained case: https://creator-assertions.github.io/training-and-data-mining/1.0/#_schema_and_example
            # Create the data block for cawg.training-mining
            training_mining_data_block = {}
            if ai_training is not None:
                training_mining_data_block["cawg.ai_training"] = {"use": ai_training}
                if ai_training == "constrained" and ai_training_constraint_info:
                    training_mining_data_block["cawg.ai_training"]["constraint_info"] = ai_training_constraint_info

            if ai_generative_training is not None:
                training_mining_data_block["cawg.ai_generative_training"] = {"use": ai_generative_training}
                if ai_generative_training == "constrained" and ai_generative_training_constraint_info:
                    training_mining_data_block["cawg.ai_generative_training"]["constraint_info"] = ai_generative_training_constraint_info

            if data_mining is not None:
                training_mining_data_block["cawg.data_mining"] = {"use": data_mining}
                if data_mining == "constrained" and data_mining_constraint_info:
                    training_mining_data_block["cawg.data_mining"]["constraint_info"] = data_mining_constraint_info

            if ai_inference is not None:
                training_mining_data_block["cawg.ai_inference"] = {"use": ai_inference}
                if ai_inference == "constrained" and ai_inference_constraint_info:
                    training_mining_data_block["cawg.ai_inference"]["constraint_info"] = ai_inference_constraint_info

            # Only create the cawg.training-mining structure if there is data to include
            if training_mining_data_block:
                training_mining_data = {
                    "label": "cawg.training-mining",
                    "data": training_mining_data_block
                }
            else:
                training_mining_data = None

            manifest_json = {
                "claim_generator_info": [{
                    "name": "long_tailed_leopard",
                    "version": "0.1"
                }],
                "title": "Do Not Train with Contact Information",
                "assertions": []
            }

            #this is meant to sort the dict so it write the assertions in alphabetical order.  This is not necessary, but it is nice to have.
            entries = OrderedDict()

            # Add the training_mining_data to assertions if it exists
            if training_mining_data:
                manifest_json["assertions"].append(training_mining_data)

                # Iterate over the kwargs and add them to entries if they exist
                for key, value in kwargs.items():
                    if value is not None:
                        entries[f"Iptc4xmpExt:{key}"] = value

                if entries:
                    manifest_json["assertions"].append({
                        "label": "cawg.metadata",
                        "data": {
                            "@context": {
                                "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
                                "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/"
                            },
                            **entries,
                        }
                    })

                    logger.info ("Compiled manifest: ", manifest_json)
        except Exception as e:
            logger.error(f"Error compiling manifest: {e}")
        
        # Directory where the file will be saved
        # For a prod env, this should be an S3 bucket or similar
        output_dir = os.path.join('processed_files')
        logger.info(f"Processing file {file.name}")

        # Ensure the output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Generate a unique file name, e.g., using a timestamp
        # This example assumes the file variable is a Werkzeug FileStorage object (Flask file upload)
        original_filename = file.name
        filename, file_extension = os.path.splitext(original_filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"{filename}_{timestamp}{file_extension}"
        save_path = os.path.join(output_dir, new_filename)

        # Save the file
        with open(save_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # Get the certs
        certs = get_certs()

    # create signer, with prod and dev paths
        if env == 'prod':
            try:
                logger.debug(f"certs type: {type(certs)}")
                signer = create_signer(kms_sign, SigningAlg.PS256, certs, "http://timestamp.digicert.com")
                logger.info(f"Signer created: {signer}")
            except Exception as e:
                logger.error(f"Error creating signer: {e}")
        else:
            try:
                logger.debug(f"certs type: {type(certs)}")
                signer = create_signer(dev_private_sign,SigningAlg.PS256,certs,"http://timestamp.digicert.com")
                logger.info(f"Signer created: {signer}")
            except Exception as e:
                logger.error(f"Error creating signer: {e}")

        # Create a builder
        try: builder = Builder(manifest_json)
        except Exception as e:
            logger.error(f"Error creating builder: {e}")

        #recreating the save path to be the same as the original filename and setting the new read path to the save path for signing.
        read_path = save_path
        save_path = os.path.join(output_dir, original_filename)

        logger.info(f'read_path: {read_path} and save_path: {save_path}')

        # Sign and add our manifest to a source file, writing it to an output file.
        # This returns the binary manifest data that could be uploaded to cloud storage.
        logger.info(f"Signing manifest and adding it to the file")

        # Additional logging before calling sign_file
        logger.debug(f"Calling sign_file with signer: {signer}, read_path: {read_path}, save_path: {save_path}")
        logger.debug(f"signer type: {type(signer)}, read_path type: {type(read_path)}, save_path type: {type(save_path)}")

        signed_file = await sign_manifest(builder, signer, read_path, save_path)

        return signed_file, new_filename
    except Exception as e:
        record_id = copy_kwargs.get('record_id', None)
        if not record_id:
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
            if any(save_path.lower().endswith(ext) for ext in video_extensions):
                s3_url = s3_obj.upload_video(local_video_path=save_path, user_email=user_email, original_filename=original_filename)
            else:
                s3_url = s3_obj.upload_image(local_image_path=save_path, user_email=user_email, original_filename=original_filename)

            try:
                db_user = await sync_to_async(OrgUser.objects.get)(email=user_email)
            except Exception as e:
                db_user = None
            
            if db_user:
                imagestatus = await sync_to_async(ImageStatus.objects.create)(
                    image_name=original_filename,
                    image_url=s3_url,
                    image_status='failed',
                    user_id=db_user,
                    meta_data=json.dumps(copy_kwargs),
                )

        if os.path.exists(save_path):
            os.remove(save_path)

        processed_path = f"processed_files/{save_path}"
        if os.path.exists(processed_path):
            os.remove(processed_path)

        logger.info(f"Download link: {save_path}")
        logger.info(f"Download link: {save_path}")
       
    ###### Need to use this to create the signing and metadata addinging logic above.  This should provide a template for that.
    ###### Add Signed C2PA Manifest to the file (https://github.com/contentauth/c2pa-python?tab=readme-ov-file#add-a-signed-manifest-to-a-media-file)

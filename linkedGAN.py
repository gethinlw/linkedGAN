from requests import get, put, post
from requests.models import Response
import boto3
import botocore.client
from io import BytesIO
from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from typing import Tuple
from json import loads
import logging
from urllib import parse


def main() -> None:
    logging.basicConfig(format='%(asctime)s - %(levelname)s [%(filename)s(%(funcName)s)] - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S %z',
                        level=logging.INFO
                        )

    # Retrieve sensitive parameters from the AWS Simple Systems Manager Parameter Store (securestrings)
    client: botocore.client = boto3.client('ssm')
    linkedin_profile_page: str = get_param(client, 'linkedGAN_linkedin_profile_page') # Your linkedin profile page url
    encoded_profile_urn: str = get_param(client, 'linkedGAN_encoded_profile_urn') # HTML-encoded profile urn
    cookies: dict = loads(get_param(client, 'linkedGAN_cookies')) # Cookies as a JSON string of k,v pairs, all strings
    # Cookies required are 'bcookie', 'bscookie', 'li_mc', 'li_rm', 'li_gc', 'liap', 'li_at', 'JSESSIONID'
        
    # Set non-sensitive parameters
    gan_image_url: str = 'https://thispersondoesnotexist.com/image'
    metadata_api_url: str = 'https://www.linkedin.com/voyager/api/voyagerMediaUploadMetadata'
    profile_api_url: str = f'https://www.linkedin.com/voyager/api/identity/dash/profiles/{encoded_profile_urn}'
    request_headers: dict = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '\
                                    'Chrome/92.0.4515.131 Safari/537.36',
        'accept': 'application/vnd.linkedin.normalized+json+2.1',
        'csrf-token': cookies.get('JSESSIONID','')[1:-1],
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': linkedin_profile_page,
        'Accept-Language': 'en-GB,en;q=0.9',
        'Host': 'www.linkedin.com',
        'X-Restli-Protocol-Version': '2.0.0'
    }

    # Get a GAN image, process it (scale to 400x400 and apply an overlay)
    r: Response = get(gan_image_url)
    check_request_result(r, 'GAN image download')
    gan_image: bytes = process_image(r.content)

    # Register the image metadata with Linkedin, then get complete upload URLs from the response data (once metadata 
    # has been supplied, the responses include instructions for where to upload the images) and urns to use when 
    # setting the profile images.
    original_upload_url: str
    original_urn: str
    display_upload_url: str
    display_urn: str
    original_upload_url, original_urn = register_metadata(metadata_api_url, gan_image, True, headers=request_headers,
                                                            cookies=cookies)
    display_upload_url, display_urn = register_metadata(metadata_api_url, gan_image, False, headers=request_headers,
                                                            cookies=cookies)

    # Get shortened upload url (minus the params) and upload params for Original and Display upload URLs (since they're
    # used separately but supplied by Linkedin in combined form)
    short_original_upload_url: str
    original_upload_params: dict
    short_display_upload_url: str
    display_upload_params: dict
    short_original_upload_url, original_upload_params = parse_upload_url(original_upload_url)
    short_display_upload_url, display_upload_params = parse_upload_url(display_upload_url)

    # Make some additional headers for upload content type & size, add them to the default headers to allow file upload
    image_content_headers: dict = {
        'Content-Length': str(len(gan_image)),
        'Content-Type': 'image/jpeg'
    }
    upload_headers: dict = {**request_headers, **image_content_headers}

    # Upload the "original" and "display" images
    r: Response = put(short_original_upload_url, data=gan_image, headers=upload_headers, cookies=cookies,
                                params=original_upload_params, timeout=5)
    check_request_result(r, 'upload original picture')
    
    r: Response = put(short_display_upload_url, data=gan_image, headers=upload_headers, cookies=cookies,
                                params=display_upload_params, timeout=5)
    check_request_result(r, 'upload display picture')

    # Make a payload for setting profile images to the uploaded images, send to LinkedIn to set the profile image
    picture_set_data: str = '{"patch": {"profilePicture": {"$set": {"originalImageUrn": "' + original_urn + '","'\
                                                                    'displayImageUrn": "' + display_urn + r'"}}}}'
    r: Response = post(profile_api_url, data=picture_set_data, headers=request_headers,
                                params={'versionTag': '418268983'}, cookies=cookies, timeout=5)
    check_request_result(r, 'set profile picture')


def process_image(image: bytes) -> bytes:
    """
    Resize an image to 400x400 and overlay a semitransparent png image on top.

    Args:
        image (bytes): The input image as a bytestream. It should be square, otherwise it'll be returned distorted.

    Returns:
        bytes: The processed image as a jpeg bytestream.
    """

    # Load the image into a Pillow image from a bytestream and resize it
    pil_image: Image.Image = Image.open(BytesIO(image)).resize((400,400))

    # Open the overlay template and paste over the GAN image
    overlay: PngImageFile = Image.open('overlay.png')
    pil_image.paste(overlay, (0,0), overlay)

    # Create a byte file and use it to save a jpeg of the processed file
    byte_file: BytesIO = BytesIO()
    pil_image.save(byte_file, 'jpeg')

    return byte_file.getvalue()


def register_metadata(metadata_api_url: str, image: bytes, is_orig: bool, **kwargs) -> Tuple[str, str]:
    """
    Send metadata to LinkedIn describing the files that will be uploaded (name & size).

    Args:
        metadata_api_url (str): The API endpoint for metadata registration.
        image (bytes): The image being uploaded, only needed for file size.
        is_orig (bool): Whether this is the Original profile image or the Display image.
    
    Kwargs:
        headers (dict): Request headers to pass with the API call.
        cookies (dict): Cookies to pass with the API call.

    Returns:
        Tuple[str, str]: The URL that should be used for image upload, and the file's assigned LinkedIn urn.
    """

    # Create upload metadata payload for the "original" and "display" images (Linkedin needs this, even though they're
    # the same image)
    metadata: str = f'{{"mediaUploadType":"PROFILE_{"ORIGINAL" if is_orig else "DISPLAY"}_PHOTO",'\
                    f'"fileSize":{str(len(image))},"filename":"pic{"" if is_orig else "-display"}.jpeg"}}'

    action: str = f'{"original" if is_orig else "display"} image metadata registration'

    # Register the metadata with LinkedIn
    r: Response = post(metadata_api_url, data=metadata, **kwargs, params={'action': 'upload'}, timeout=5)
    check_request_result(r, action)
    
    # Parse the returned data to retrieve the upload url and urn
    r_data: dict = loads(r.text)
    upload_url: str = r_data.get('data', {}).get('value', {}).get('singleUploadUrl', '')
    urn: str = r_data.get('data', {}).get('value', {}).get('urn', '')

    if upload_url == '' or urn == '':
        raise RuntimeError(f'Missing urn or upload URL after {action}')

    return upload_url, urn


def parse_upload_url(url: str) -> Tuple[str, dict]:
    """
    Parse a full URL with parameters on the end to separate the scheme/domain/path from the paramaters.

    Args:
        url (str): The full url with parameters attached.
       
    Returns:
        Tuple[str, dict]: A tuple containing the two components.
    """

    # Parse the returned url
    parsed_url: parse.ParseResult = parse.urlparse(url)
    
    # Extract the needed bits from the parsed url
    url_without_params: str = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}'
    params: dict = {k: v[0] for k,v in parse.parse_qs(parsed_url.query).items()}

    return url_without_params, params


def check_request_result(r: Response, action: str) -> None:
    """
    Check that a Requests HTTP request was successful (didn't return None, and response code is some variety of 'Ok').

    Args:
        r (Response): The Requests response being checked.
        action (str): A description of what was being attempted to put in a log/exception message.
       
    Returns:
        None
    """

    # Check for a 2xx HTTP return code, if there was an error throw an exception to halt the script
    if r is not None and r.status_code//100 == 2:
        logging.info(f'Requests action {action!r} result: {r.status_code}')
    else:
        raise RuntimeError(f'Requests action {action!r} failed')


def get_param(client: botocore.client, param_name: str) -> str:
    """
    Retrieve a given named parameter from the AWS Simple Systems Manager (SSM) parameter store.

    Args:
        client (SSM): The boto client being used, re-used across multiple requests because of invocation overhead.
        param_name (str): The name of the parameter being retrieved.
       
    Returns:
        str: The parameter's value.
    """

    # Call the AWS SSM GetParameter API, extract the parameter's value from the response
    response_data = client.get_parameter(Name=param_name, WithDecryption=True)
    return response_data.get('Parameter', {}).get('Value', '')


if __name__ == '__main__':

    main()

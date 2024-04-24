import datetime
import io
import logging
import os
import uuid
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, HTTPException, Request, Response, File
from minio import Minio
from minio.commonconfig import Tags
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address

from discord import DiscordWebhookResponse, Author, Attachment

app = FastAPI()

app_error_log = logging.getLogger("uvicorn.error")

limiter = Limiter(key_func=get_remote_address)

Instrumentator().instrument(app).expose(app)

load_dotenv()

MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', None)
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', None)
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'handy-blobs')
MINIO_HOST = os.getenv('MINIO_HOST', 'minio-api.r3ktm8.de')

RATE_LIMIT = os.getenv('APP_RATE_LIMIT', '4/minute')

ATTACHMENT_BASE_URL = os.getenv('ATTACHMENT_BASE_URL', 'https://discord-cdn.srvc.alteravitarp.de')

REQUEST_IP_WHITELIST = os.getenv('REQUEST_IP_WHITELIST', '127.0.0.1').split(',')

minio_client = Minio(MINIO_HOST, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY)

if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
    minio_client.make_bucket(MINIO_BUCKET_NAME)


def is_file_image(file: UploadFile):
    return file.content_type.startswith('image/')


@app.middleware("http")
async def cache_control_header(request: Request, call_next):
    response = await call_next(request)

    if request.method.upper() == 'GET':
        response.headers["Cache-Control"] = "public, max-age=600"

    return response


@app.get('/image/{attachment_id}', responses={
    200: {
        "content": {
            "image/png":  {},
            "image/jpg":  {},
            "image/jpeg": {},
        },
    }
})
async def get_image(attachment_id: str) -> Response:
    _id = attachment_id.split('.')
    _uuid = _id[0]
    _attachment_type = 'png'

    if len(_id) == 2:
        _attachment_type = _id[1]

    if _attachment_type not in ['png', 'jpg', 'jpeg']:
        raise HTTPException(status_code=400, detail="Invalid attachment type")

    try:
        _id = uuid.UUID(_uuid, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid UUID')

    try:
        data = minio_client.get_object(MINIO_BUCKET_NAME, f'{attachment_id}')
    except Exception as e:
        raise HTTPException(status_code=404, detail='Image not found')

    return Response(content=data.read(), media_type=f'image/{_attachment_type}')


@app.post('/upload/{attachment_id}')
@limiter.shared_limit(RATE_LIMIT, scope="upload")
async def upload(request: Request, response: Response, attachment_id: str,
                 file: Annotated[
                     UploadFile, File(validation_alias="files[]", alias="files[]")]) -> DiscordWebhookResponse:
    try:
        _id = uuid.UUID(attachment_id, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid UUID')

    content = None
    content_type = None
    file_extension = None

    if is_file_image(file):
        content_type = file.content_type
        content = await file.read()
        file_extension = content_type.split('/')[1]

        if file_extension.lower() not in ['png', 'jpeg', 'jpg']:
            raise HTTPException(status_code=400, detail='Only PNG and JPEG/JPG images are supported')

        tmp_file_name = f'{attachment_id}.{file_extension}'

        file_tags = Tags()
        file_tags['client'] = request.client.host

        if file_tags['client'].startswith('172.'):
            app_error_log.error(f'Client IP starts with 172. which could indicate being behind a proxy.')

        minio_client.put_object(MINIO_BUCKET_NAME, tmp_file_name, io.BytesIO(content), len(content), content_type,
                                tags=file_tags)
    else:
        raise HTTPException(status_code=400, detail='File is not an image')

    if content is None:
        raise HTTPException(status_code=400, detail='No image file provided')

    attachment = Attachment(
        id=attachment_id,
        filename='image.png',
        size=len(content),
        url=f'{ATTACHMENT_BASE_URL}/image/{attachment_id}.{file_extension}',
        proxy_url=f'{ATTACHMENT_BASE_URL}/image/{attachment_id}.{file_extension}',
        width=0,
        height=0,
        content_type=content_type,
        placeholder=None,
        placeholder_version=0
    )

    author = Author(
        id="1073297612884672552",
        username="Image Server",
        bot=True,
        flags=0,
        public_flags=0,
        avatar="",
        discriminator="9983",
        global_name=None,
    )

    output = DiscordWebhookResponse(
        id='1224476078501007471',
        type=0,
        content="",
        embeds=list(),
        mentions=list(),
        attachments=list(),
        pinned=False,
        mention_everyone=False,
        timestamp=datetime.datetime.now(),
        flags=0,
        components=list(),
        webhook_id='',
        author=author,
        channel_id='1224476078501007471',
        mention_roles=list(),
        tts=False,
        edited_timestamp=None
    )

    output.attachments.append(attachment)

    return output


@app.post('/upload')
@limiter.shared_limit(RATE_LIMIT, scope="upload")
async def upload_without_id(request: Request, response: Response,
                            file: Annotated[UploadFile, File(validation_alias="files[]",
                                                             alias="files[]")], ) -> DiscordWebhookResponse:
    attachment_id = str(uuid.uuid4())

    return await upload(request, response, attachment_id, file)


@app.get("/")
async def root():
    return {"message": "Hello World"}

import datetime
import io
import os
import uuid
from typing import Annotated

from discord import DiscordWebhookResponse, Author, Attachment
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, HTTPException, Request, Response, File
from minio import Minio
from minio.commonconfig import Tags

app = FastAPI()

load_dotenv()

MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', None)
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', None)
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'handy-blobs')
MINIO_HOST = os.getenv('MINIO_HOST', 'minio-api.r3ktm8.de')

ATTACHMENT_BASE_URL = os.getenv('ATTACHMENT_BASE_URL', 'https://discord-cdn.srvc.alteravitarp.de')

minio_client = Minio(MINIO_HOST, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY)

if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
    minio_client.make_bucket(MINIO_BUCKET_NAME)


def is_file_image(file: UploadFile):
    return file.content_type.startswith('image/')


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    print(request.headers)
    print(await request.body())

    response = await call_next(request)
    response.headers["X-Process-Time"] = str(datetime.datetime.now())
    return response


@app.get('/image/{attachment_id}', responses={
    200: {
        "content": {
            "image/png": {},
            "image/jpg": {},
            "image/jpeg": {},
        },
    }
})
async def get_image(attachment_id: str) -> Response:
    _uuid = attachment_id.split(".")[0]

    try:
        _id = uuid.UUID(_uuid, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid UUID')

    try:
        data = minio_client.get_object(MINIO_BUCKET_NAME, f'{attachment_id}')
    except Exception as e:
        raise HTTPException(status_code=404, detail='Image not found')

    return Response(content=data.read(), media_type='image/png')


@app.post('/upload/{attachment_id}')
async def upload(attachment_id: str, request: Request,
                 file: Annotated[
                     UploadFile, File(validation_alias="files[0]", alias="files[0]")], ) -> DiscordWebhookResponse:
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

    response = DiscordWebhookResponse(
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

    response.attachments.append(attachment)

    return response


@app.post('/upload')
async def upload_without_id(files: Annotated[UploadFile, File(validation_alias="files[0]", alias="files[0]")],
                            request: Request) -> DiscordWebhookResponse:
    attachment_id = str(uuid.uuid4())

    return await upload(attachment_id, request, files)


@app.get("/")
async def root():
    return {"message": "Hello World"}

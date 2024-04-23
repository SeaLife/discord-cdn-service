# Discord CDN Service

As of October 2023, Discord announced to expire CDN urls after 6 weeks. In order to maintain functionality in some FiveM
scripts using Discord to store images, this service was created.

## How does it work?

This services provides the same `multipart/form-data` endpoint as Discord does. So the Service can be used as a drop-in
replacement. (https://discord.com/developers/docs/reference#uploading-files).

## How to use it?

Just deploy the service anywhere on your infrastructure and replace the "Webhook"-Url in your configurations
with: `https://your-domain.com/upload`.

In example: The Roadphone (https://fivem.roadshop.org/package/4885785) uses the Discord CDN to store images. Just
replace the URL in the `API.lua` with the one of your service.

```lua
Cfg.PhotoWebhook = "https://your-domain.com/upload"
```

## Example Deployment using docker-compose.yml

#### Step 1: Checkout the repository

```bash
git clone https://github.com/SeaLife/discord-cdn-service.git 
```

#### Step 2: Create the `docker-compose.yml`

> [!WARNING]  
> The Minio-Deployment is **not** production ready and you should consider creating a special user for the cdn service.
> This is just for demonstration.
> Check: https://min.io/docs/minio/container/administration/identity-access-management/minio-user-management.html

```yaml
services:
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    restart: unless-stopped
    volumes:
      - ./minio-data:/data
    networks:
      - discord-cdn-network
    environment:
      MINIO_ROOT_USER: JB74AW2WMTZ8LNVNXS9L2QL2P84N4WJ2
      MINIO_ROOT_PASSWORD: yG5XdzH3rGqLmeS4pbDcje+kTD5yNWdNRg6E9FWF9E

  discord-cdn-service:
    build: discord-cdn-service
    restart: unless-stopped
    ports:
      - 8080:8080
    environment:
      MINIO_ACCESS_KEY: JB74AW2WMTZ8LNVNXS9L2QL2P84N4WJ2
      MINIO_SECRET_KEY: yG5XdzH3rGqLmeS4pbDcje+kTD5yNWdNRg6E9FWF9E
      MINIO_BUCKET: discord-cdn
      MINIO_HOST: minio
      ATTACHMENT_BASE_URL: http://localhost:8080
      REQUEST_IP_WHITELIST: 127.0.0.1
    networks:
      - discord-cdn-network

networks:
  discord-cdn-network:
```

> [!IMPORTANT]  
> The CDN services tries to create the Bucket if its not there. If the access key has no permission to create buckets,
> this will cause the service to not boot up.

#### Step 3: Start the service

```bash
docker-compose up -d
```
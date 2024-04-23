from dataclasses import dataclass
from datetime import datetime
from typing import List, Any


@dataclass
class Attachment:
    id: str
    filename: str
    size: int
    url: str
    proxy_url: str
    width: int
    height: int
    content_type: str
    placeholder: Any
    placeholder_version: int


@dataclass
class Author:
    id: str
    username: str
    avatar: str
    discriminator: str
    public_flags: int
    flags: int
    bot: bool
    global_name: Any


@dataclass
class DiscordWebhookResponse:
    id: str
    type: int
    content: str
    channel_id: str
    author: Author
    attachments: List[Attachment]
    embeds: List[Any]
    mentions: List[Any]
    mention_roles: List[Any]
    pinned: bool
    mention_everyone: bool
    tts: bool
    timestamp: datetime
    edited_timestamp: Any
    flags: int
    components: List[Any]
    webhook_id: str

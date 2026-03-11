import asyncio

from telethon.errors import FileMigrateError
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import InputDocumentFileLocation

from config import CHUNK_SIZE


class ChunkDownloader:
    def __init__(self, client, document, path: str):
        self.client = client
        self.document = document
        self.path = path
        self.file_dc_id = None
        self.sender_cache = {}
        self.file_lock = asyncio.Lock()

    def _build_location(self):
        return InputDocumentFileLocation(
            id=self.document.id,
            access_hash=self.document.access_hash,
            file_reference=self.document.file_reference,
            thumb_size="",
        )

    async def _get_sender(self, dc_id: int):
        if dc_id in self.sender_cache:
            return self.sender_cache[dc_id]
        sender = await self.client._borrow_exported_sender(dc_id)
        self.sender_cache[dc_id] = sender
        return sender

    async def _request(self, offset: int):
        request = GetFileRequest(
            location=self._build_location(),
            offset=offset,
            limit=CHUNK_SIZE,
        )
        if self.file_dc_id is None:
            return await self.client(request)
        sender = await self._get_sender(self.file_dc_id)
        return await self.client._call(sender, request)

    async def download_chunk(self, offset: int) -> int:
        try:
            result = await self._request(offset)
        except FileMigrateError as exc:
            self.file_dc_id = exc.new_dc
            sender = await self._get_sender(self.file_dc_id)
            result = await self.client._call(
                sender,
                GetFileRequest(
                    location=self._build_location(),
                    offset=offset,
                    limit=CHUNK_SIZE,
                ),
            )

        data = result.bytes
        async with self.file_lock:
            with open(self.path, "r+b") as f:
                f.seek(offset)
                f.write(data)
        return len(data)

    async def close(self):
        for sender in self.sender_cache.values():
            await self.client._return_exported_sender(sender)
        self.sender_cache.clear()

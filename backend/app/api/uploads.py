"""Leitura de uploads com limite de tamanho.

Lê o arquivo em blocos e aborta ao ultrapassar o limite, evitando carregar
arquivos arbitrariamente grandes em memória.
"""

from __future__ import annotations

from fastapi import UploadFile

from app.core.errors import ImageTooLargeError

CHUNK_SIZE = 64 * 1024


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ImageTooLargeError(details={"max_image_size_bytes": max_bytes})
        chunks.append(chunk)
    return b"".join(chunks)

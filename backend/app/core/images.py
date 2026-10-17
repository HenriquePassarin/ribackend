"""Validação de imagens recebidas por upload.

A validação aqui é estrutural (assinatura do arquivo) e serve para rejeitar
arquivos que claramente não são imagens dos formatos suportados. Não confiamos
no Content-Type nem na extensão informados pelo cliente.

Limitação conhecida: não decodificamos a imagem. Quando um modelo real for
integrado, o próprio framework de inferência deverá validar/decodificar a
imagem antes do pré-processamento.
"""

from __future__ import annotations

PNG = "png"
JPEG = "jpeg"
GIF = "gif"
WEBP = "webp"
BMP = "bmp"
TIFF = "tiff"
HEIF = "heif"

# Formatos aceitos pelo adaptador de visão implementado neste projeto.
SUPPORTED_FORMATS: frozenset[str] = frozenset({PNG, JPEG})

# Tipos declarados que podem ser aceitos (o conteúdo real é validado à parte).
DECLARED_MIME_TYPES: frozenset[str] = frozenset({"image/png", "image/jpeg", "image/jpg"})


def sniff_format(content: bytes) -> str | None:
    """Detecta o formato real a partir dos bytes iniciais.

    Retorna o nome do formato detectado ou ``None`` se o conteúdo não
    corresponder a nenhuma assinatura conhecida. Detectar formatos não
    suportados permite responder 415 (tipo não suportado) em vez de 400
    (conteúdo inválido) quando o cliente envia uma imagem válida de formato
    não suportado.
    """
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return WEBP
    if content.startswith(b"BM"):
        return BMP
    if content.startswith(b"II*\x00") or content.startswith(b"MM\x00*"):
        return TIFF
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return HEIF
    return None

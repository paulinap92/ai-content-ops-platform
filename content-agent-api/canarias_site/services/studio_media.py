"""Bounded image uploads to the existing optional R2 object store."""
import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select, text

from canarias_site.models.studio import StudioDocument, StudioAsset
from canarias_site.utils.islands import VALID_ISLANDS

R2_KEYS = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE_URL")


def enabled():
    return True


def r2_enabled():
    return all(os.getenv(k) for k in R2_KEYS)


def image_data(encoded: str):
    if len(encoded) > 7_000_000:
        raise ValueError("Zdjęcie może mieć najwyżej 5 MB.")
    data = base64.b64decode(encoded, validate=True)
    if not data or len(data) > 5_000_000:
        raise ValueError("Zdjęcie może mieć najwyżej 5 MB.")
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return data, "image/webp", "webp"
    raise ValueError("Obsługiwane zdjęcia: JPEG, PNG i WebP.")


def signed_upload(data, mime, key, *, now=None):
    account, bucket, access, secret, public_base = (os.environ[k] for k in R2_KEYS)
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or not public_base.startswith("https://"):
        raise ValueError("Nieprawidłowa konfiguracja biblioteki zdjęć.")
    now = now or datetime.now(timezone.utc)
    stamp, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    host = f"{account}.r2.cloudflarestorage.com"
    path = f"/{bucket}/{key}"
    digest = hashlib.sha256(data).hexdigest()
    headers = {"content-type": mime, "host": host, "x-amz-content-sha256": digest, "x-amz-date": stamp}
    names = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical = f"PUT\n{path}\n\n{canonical_headers}\n{names}\n{digest}"
    scope = f"{date}/auto/s3/aws4_request"
    signing = ("AWS4" + secret).encode()
    for part in (date, "auto", "s3", "aws4_request"):
        signing = hmac.new(signing, part.encode(), hashlib.sha256).digest()
    string_to_sign = f"AWS4-HMAC-SHA256\n{stamp}\n{scope}\n{hashlib.sha256(canonical.encode()).hexdigest()}"
    signature = hmac.new(signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={names}, Signature={signature}"
    return f"https://{host}{path}", headers, public_base.rstrip("/") + "/" + key


async def upload(session, island, filename, encoded, alt="", credit=""):
    from sqlalchemy import func
    if island not in VALID_ISLANDS:
        raise ValueError("Unknown island")
    data, mime, ext = image_data(encoded)
    digest = hashlib.sha256(data).hexdigest()
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"studio-media:{island}:{digest}"})
    row = await session.scalar(select(StudioDocument).where(StudioDocument.kind == "media", StudioDocument.island == island, StudioDocument.record_key == digest))
    if row:
        return {**row.published,"media_id":str(row.id),"island":row.island}
    if r2_enabled():
        key=f"editor/{digest}.{ext}";url,headers,public_url=signed_upload(data,mime,key)
        async with httpx.AsyncClient(timeout=40,follow_redirects=False) as client:
            response=await client.put(url,content=data,headers=headers)
            if response.status_code not in {200,201,204}:raise HTTPException(502,"Biblioteka zdjęć odrzuciła plik.")
    else:
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('studio-assets-quota',0))"))
        asset=await session.get(StudioAsset,digest)
        if not asset:
            used=await session.scalar(select(func.coalesce(func.sum(func.octet_length(StudioAsset.data)),0)))
            if used+len(data)>100_000_000:raise HTTPException(413,"Biblioteka osiągnęła limit 100 MB. Zmniejsz zdjęcie lub skonfiguruj większy magazyn R2.")
            session.add(StudioAsset(digest=digest,mime_type=mime,data=data,created_at=datetime.now(timezone.utc)))
        public_url=os.getenv('CANARIAS_PUBLIC_API_URL','https://canarias-cerca-api.onrender.com').rstrip('/')+'/api/media/'+digest
    payload={"url":public_url,"filename":filename[:180],"mime_type":mime,"size":len(data),"alt":alt[:300],"credit":credit[:200]}
    row=StudioDocument(id=uuid4(), kind="media", island=island, resource="images", record_key=digest, draft=payload, published=payload, base_fingerprint=digest, version=1, status="published", updated_at=datetime.now(timezone.utc))
    session.add(row)
    await session.commit()
    return {**payload,"media_id":str(row.id),"island":row.island}

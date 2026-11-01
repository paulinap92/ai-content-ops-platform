import pytest
from sqlalchemy.dialects import postgresql
from canarias_site.services.studio import fingerprint, validate_identity, validate_payload
from canarias_site.services.editorial_privacy import public_payload
from canarias_site.services.site_settings import normalize_settings, effective_settings, empty_settings
from canarias_site.services.studio_media import image_data, signed_upload


def identity(kind="guide", resource="food"):
    return {"kind":kind,"island":"tenerife","resource":resource,"record_key":"new:test"}



def test_private_metadata_never_reaches_public_json():
    source={"name":"Papas", "editor_notes":["PRIVATE"], "translations":{"es":{"body_markdown":"Public", "editor_notes":"PRIVATE"}}, "tags":["food"]}
    result=public_payload(source)
    assert result=={"name":"Papas","translations":{"es":{"body_markdown":"Public"}},"tags":["food"]}
    assert source["editor_notes"]==["PRIVATE"]



def test_settings_preserve_island_overrides_and_do_not_coerce_false():
    settings=normalize_settings({"global":{"sections":{"guide":False},"features":{"guide.food":False}},"islands":{"tenerife":{"sections":{"guide":True}}}})
    assert effective_settings(settings,"tenerife")["sections"]["guide"] is True
    assert effective_settings(settings,"la-palma")["sections"]["guide"] is False
    with pytest.raises(ValueError):
        normalize_settings({"global":{"sections":{"guide":"false"}}})
    with pytest.raises(ValueError):
        normalize_settings({"islands":{"made-up-island":{}}})
    with pytest.raises(ValueError):
        normalize_settings({"global":{"features":{"guide.secret":False}}})



def test_fingerprint_is_stable_for_json_key_order_and_changes_for_content():
    assert fingerprint({"b":2,"a":"España"})==fingerprint({"a":"España","b":2})
    assert fingerprint({"b":2})!=fingerprint({"b":3})



def test_regional_scope_is_available_only_for_news():
    regional = {**identity("news", "news"), "island": "canarias"}
    assert validate_identity(regional) == regional
    with pytest.raises(ValueError):
        validate_identity({**identity(), "island": "canarias"})



@pytest.mark.parametrize("kind,resource",[("guide","food"),("explore","routes"),("calendar","2026-11"),("news","news")])
def test_only_declared_editorial_resources_are_supported(kind,resource):
    assert validate_identity(identity(kind,resource))
    with pytest.raises(ValueError):
        validate_identity(identity("live","weather"))
    with pytest.raises(ValueError):
        validate_identity(identity("guide","sql"))



@pytest.mark.parametrize("payload",[{"name":"X","slug":"x","image_url":"javascript:alert(1)"},{"name":"X","slug":"x","latitude":1000},{"name":"X","slug":"x","hidden":"false"},{"name":"","slug":"x"}])
def test_invalid_editorial_values_are_rejected(payload):
    with pytest.raises(ValueError):
        validate_payload(identity(),payload)



def test_images_reject_active_formats_and_oversized_payloads():
    import base64
    with pytest.raises(ValueError):
        image_data(base64.b64encode(b"<svg onload='alert(1)'></svg>").decode())
    with pytest.raises(ValueError):
        image_data("a"*7_000_001)
    assert image_data(base64.b64encode(b"\xff\xd8\xfftest").decode())[1:]==("image/jpeg","jpg")



def test_r2_upload_signature_has_fixed_destination_and_does_not_expose_secret(monkeypatch):
    values={"R2_ACCOUNT_ID":"a"*32,"R2_BUCKET":"cc-test-images","R2_ACCESS_KEY_ID":"public-key-id","R2_SECRET_ACCESS_KEY":"private-secret-value","R2_PUBLIC_BASE_URL":"https://images.example"}
    for k,v in values.items():monkeypatch.setenv(k,v)
    url,headers,public=signed_upload(b"image","image/jpeg","editor/test.jpg")
    assert url=="https://"+"a"*32+".r2.cloudflarestorage.com/cc-test-images/editor/test.jpg"
    assert public=="https://images.example/editor/test.jpg"
    assert "private-secret-value" not in str(headers)
    assert "AWS4-HMAC-SHA256" in headers["authorization"]



@pytest.mark.asyncio
async def test_public_guide_queries_filter_drafts_before_limit():
    from canarias_site.repositories.guide_content import GuideContentRepository
    class Result:
        def all(self): return []
        def first(self): return None
    class Session:
        statement=None
        async def scalars(self,statement): self.statement=statement;return Result()
    session=Session();repo=GuideContentRepository(session)
    await repo.find_items(island="tenerife",section="food",limit=10)
    sql=str(session.statement.compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds":True}))
    assert "publication_status = 'published'" in sql
    await repo.find_item_by_slug(island="tenerife",section="food",slug="test")
    assert "publication_status" in str(session.statement)


"""Remove private editorial metadata from public payloads recursively."""
PRIVATE_FIELDS = {"editor_notes", "content_ops_status", "studio_notes", "publication_history"}


def public_payload(value):
    if isinstance(value, dict):
        return {k: public_payload(v) for k, v in value.items() if k not in PRIVATE_FIELDS and not k.startswith("_studio")}
    if isinstance(value, list):
        return [public_payload(v) for v in value]
    return value

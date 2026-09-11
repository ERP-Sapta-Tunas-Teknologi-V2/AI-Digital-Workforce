from minio import Minio
from datetime import timezone, datetime
from minio.commonconfig import CopySource
import io
import config

client = Minio(
    config.MINIO_ENDPOINT,
    access_key=config.MINIO_ACCESS_KEY,
    secret_key=config.MINIO_SECRET_KEY,
    secure=config.MINIO_SECURE,
)

def ensure_bucket():
    if not client.bucket_exists(config.MINIO_BUCKET):
        client.make_bucket(config.MINIO_BUCKET)

def object_key(category: str, filename: str) -> str:
    return f"{category}/{filename}"

def file_exists(category: str, filename: str) -> bool:
    try:
        client.stat_object(config.MINIO_BUCKET, object_key(category, filename))
        return True
    except Exception:
        return False

def upload_file(category: str, filename: str, file_stream, length: int, content_type: str):
    client.put_object(
        config.MINIO_BUCKET,
        object_key(category, filename),
        file_stream,
        length=length,
        content_type=content_type
    )

def list_files(category: str = None):
    prefix = f"{category}/" if category else ""
    objects = client.list_objects(config.MINIO_BUCKET, prefix=prefix, recursive=True)

    results = []
    for obj in objects:
        parts = obj.object_name.split("/", 1)
        results.append({
            "category": parts[0],
            "filename": parts[1] if len(parts) > 1 else parts[0],
            "path": obj.object_name,
            "uploaded_at": obj.last_modified.astimezone(timezone.utc).isoformat() if obj.last_modified else None,
            "size": obj.size
        })
    return results

def download_path(category: str, filename: str) -> str:
    """Return local temp path for pipeline use if needed, or object path for reference."""
    return object_key(category, filename)

def delete_file(category: str, filename: str):
    client.remove_object(
        config.MINIO_BUCKET,
        object_key(category, filename)
    )

def download_file(category: str, filename: str):
    response = client.get_object(
        config.MINIO_BUCKET,
        object_key(category, filename)
    )

    try:
        data = response.read()
    finally:
        response.close()
        response.release_conn()

    return io.BytesIO(data)

def archive_file(category: str, filename: str):
    """Pindahkan file ke folder _archive dengan timestamp, bukan dihapus permanen."""
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    src_key = object_key(category, filename)
    dst_key = f"{category}/_archive/{timestamp}_{filename}"

    client.copy_object(
        config.MINIO_BUCKET,
        dst_key,
        CopySource(config.MINIO_BUCKET, src_key)
    )
    client.remove_object(config.MINIO_BUCKET, src_key)

    return dst_key
from app.db.db import ImageRecord
from app.schemas import ImageMetadata

def save_image_metadata_list(db, metadata_list: list[ImageMetadata]):
    for meta in metadata_list:
        record = ImageRecord(
            book_id=meta.book_id,
            source_pdf=meta.source_pdf,
            page_number=meta.page_number,
            xref=meta.xref,
            filename=meta.filename,
            caption=meta.caption,
        )
        db.add(record)
    db.commit()

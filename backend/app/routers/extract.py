from fastapi import APIRouter, HTTPException
from app.utils.minio_client import get_minio_client
import requests
import io
import fitz  # PyMuPDF

router = APIRouter()

MINIO_BUCKET = "uploads"
UNSTRUCTURED_API_URL = "http://unstructured_custom:8000/parse/"

minio_client = get_minio_client()

def extract_first_5_pages(pdf_bytes: bytes) -> io.BytesIO:
    original_doc = None
    new_doc = None
    try:
        original_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        new_doc = fitz.open()

        for i in range(min(5, len(original_doc))):
            new_doc.insert_pdf(original_doc, from_page=i, to_page=i)

        output = io.BytesIO()
        new_doc.save(output)
        output.seek(0)
        return output
    finally:
        if original_doc:
            original_doc.close()
        if new_doc:
            new_doc.close()


@router.post("/extract/")
def extract_text(filename: str):
    try:
        response = minio_client.get_object(MINIO_BUCKET, filename)
        try:
            file_data = response.read()
        finally:
            response.close()
            response.release_conn()
        file_stream = io.BytesIO(file_data)

        try:
            files = {"files": (filename, file_stream, "application/pdf")}
            res = requests.post(UNSTRUCTURED_API_URL, files=files)
        finally:
            file_stream.close()

        if res.status_code != 200:
            raise Exception(res.text)

        elements = res.json()
        text = "\n".join(e.get("text", "") for e in elements if e.get("text"))

        return {
            "filename": filename,
            "extracted_characters": len(text),
            "preview": text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/preview/")
def extract_preview(filename: str):
    try:
        response = minio_client.get_object(MINIO_BUCKET, filename)
        try:
            file_data = response.read()
        finally:
            response.close()
            response.release_conn()

        short_pdf = extract_first_5_pages(file_data)
        try:
            files = {"files": (filename, short_pdf, "application/pdf")}
            res = requests.post(UNSTRUCTURED_API_URL, files=files)
        finally:
            short_pdf.close()

        if res.status_code != 200:
            raise Exception(res.text)

        elements = res.json()
        text = "\n".join(e.get("text", "") for e in elements if e.get("text"))

        return {
            "filename": filename,
            "pages_processed": 5,
            "extracted_characters": len(text),
            "preview": text[:500]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

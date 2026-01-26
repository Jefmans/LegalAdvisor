from langchain_community.document_loaders import PyMuPDFLoader
from app.utils.minio_utils import download_from_minio


def read_pdf_from_minio(filename: str, bucket: str = "uploads") -> list:
    local_path = download_from_minio(filename, bucket=bucket)
    loader = PyMuPDFLoader(local_path)
    return loader.load()





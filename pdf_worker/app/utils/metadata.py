import logging
import os

import fitz  # PyMuPDF
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.models import DocumentMetadata

logger = logging.getLogger(__name__)


def get_doc_info(file_path: str):
    with fitz.open(file_path) as doc:
        num_pages = len(doc)
        n_pages = 10
        page_indices = list(range(min(n_pages, num_pages))) + list(
            range(max(num_pages - n_pages, 0), num_pages)
        )

        candidate_pages = []
        for i in page_indices:
            candidate_pages.append(doc[i].get_text())
    combined_text = "\n---\n".join(candidate_pages)

    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    parser = PydanticOutputParser(pydantic_object=DocumentMetadata)
    prompt = PromptTemplate(
        template="Extract the metadata from this text:\n\n{text}\n\n{format_instructions}",
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        return chain.invoke({"text": combined_text})
    except Exception as e:
        logger.exception("Metadata parsing failed: %s", e)
        return None





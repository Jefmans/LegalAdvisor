from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from elasticsearch import Elasticsearch
import os

def get_vectorstore(index_name="pdf_chunks"):
    es = Elasticsearch("http://elasticsearch:9200")  # or use ENV
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    return ElasticsearchStore(
        es_connection=es,
        index_name=index_name,
        embedding=embeddings,
        vector_query_field="vector",
        query_field="text",
        metadata_field="metadata",
    )

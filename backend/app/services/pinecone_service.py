from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
import time
from tenacity import retry, stop_after_attempt, wait_exponential

class PineconeService:
    def __init__(self):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.dimension = 1536
        self._ensure_index_exists()
        self.index = self.pc.Index(self.index_name)

    def _ensure_index_exists(self):
        if self.index_name not in self.pc.list_indexes().names():
            print(f"Creating Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.PINECONE_ENV
                )
            )
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upsert_vectors(self, vectors, namespace):
        """
        vectors: list of (id, embedding, metadata) tuples
        """
        self.index.upsert(vectors=vectors, namespace=namespace)

    def query_vectors(self, vector, namespace, top_k=5):
        # Ensure vector is a list of floats
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()
        
        return self.index.query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            include_metadata=True
        )

    def delete_vectors(self, namespace: str, filter: dict = None, ids: list = None):
        """
        Delete vectors by filter or ids.
        """
        try:
            if filter:
                self.index.delete(filter=filter, namespace=namespace)
            elif ids:
                self.index.delete(ids=ids, namespace=namespace)
        except Exception as e:
            print(f"Error deleting vectors in namespace {namespace}: {e}")
            raise

    def delete_namespace(self, namespace):
        """
        Delete all vectors in a namespace
        """
        try:
            self.index.delete(delete_all=True, namespace=namespace)
        except Exception as e:
            print(f"Error deleting namespace {namespace}: {e}")
            raise

pinecone_service = PineconeService()

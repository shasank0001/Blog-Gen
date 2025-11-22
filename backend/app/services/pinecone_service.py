from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
import time

class PineconeService:
    def __init__(self):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = "content-strategist-index"
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
                    region="us-east-1"
                )
            )
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)

    def upsert_vectors(self, vectors, namespace):
        """
        vectors: list of (id, embedding, metadata) tuples
        """
        self.index.upsert(vectors=vectors, namespace=namespace)

    def query_vectors(self, vector, namespace, top_k=5):
        return self.index.query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            include_metadata=True
        )

pinecone_service = PineconeService()

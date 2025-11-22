from langchain_text_splitters import RecursiveCharacterTextSplitter

class ChunkingService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False,
        )

    def split_text(self, text: str):
        return self.text_splitter.split_text(text)

    def split_documents(self, pages_content):
        """
        pages_content: list of dicts with 'text' and 'metadata'
        """
        chunks = []
        for page in pages_content:
            page_chunks = self.text_splitter.split_text(page["text"])
            for i, chunk in enumerate(page_chunks):
                chunks.append({
                    "text": chunk,
                    "metadata": {
                        **page["metadata"],
                        "chunk_index": i
                    }
                })
        return chunks

chunking_service = ChunkingService()

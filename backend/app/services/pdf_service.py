import fitz  # PyMuPDF

class PDFService:
    def extract_text(self, file_content: bytes) -> str:
        doc = fitz.open(stream=file_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text

    def extract_text_with_metadata(self, file_content: bytes, filename: str):
        doc = fitz.open(stream=file_content, filetype="pdf")
        pages_content = []
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages_content.append({
                    "text": text,
                    "metadata": {
                        "source": filename,
                        "page": page_num + 1
                    }
                })
        return pages_content

pdf_service = PDFService()

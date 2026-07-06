from dotenv import load_dotenv
load_dotenv()

import os # noqa: E402
from langchain_core.documents import Document # noqa: E402
from langchain_google_genai import GoogleGenerativeAIEmbeddings # noqa: E402
from langchain_chroma import Chroma # noqa: E402

DATA_DIR = "rag/data"
CHROMA_DIR = "rag/chroma_db"

def load_documents():
    documents = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".txt"):
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            documents.append(
                Document(page_content=text, metadata={"source": filename})
            )
    return documents


def main():
    documents = load_documents()
    print(f"Loaded {len(documents)} documents")

    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
    
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    print(f"Saved {len(documents)} documents to Chroma at {CHROMA_DIR}")
    
if __name__ == "__main__":
    main()
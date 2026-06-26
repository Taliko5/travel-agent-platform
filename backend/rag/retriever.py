from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

CHROMA_DIR = "rag/chroma_db"

embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings
)


def retrieve_context(query: str, k: int = 2) -> str:
    """Search for relevant documents based on the query."""
    results = vectorstore.similarity_search(query, k=k)
    context = "\n\n".join(doc.page_content for doc in results)
    return context

if __name__ == "__main__":
    test_query = "Where can I see beautiful nature and enjoy local food?"
    result = retrieve_context(test_query)
    print("=== Retrieved Context ===")
    print(result)
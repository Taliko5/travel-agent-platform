"""
Unit tests for rag/retriever.py — retrieve_context, with get_vectorstore mocked
(the lazy-init pattern means no real ChromaDB/embedding call happens here).
"""

from unittest.mock import MagicMock, patch


def _mock_doc(content):
    doc = MagicMock()
    doc.page_content = content
    return doc


class TestRetrieveContext:
    def test_passes_k_through_to_similarity_search(self):
        from rag.retriever import retrieve_context

        with patch("rag.retriever.get_vectorstore") as mock_get_vs:
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [_mock_doc("doc one")]
            mock_get_vs.return_value = mock_vs

            retrieve_context("best beaches", k=3)

            mock_vs.similarity_search.assert_called_once_with("best beaches", k=3)

    def test_default_k_is_two(self):
        from rag.retriever import retrieve_context

        with patch("rag.retriever.get_vectorstore") as mock_get_vs:
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = []
            mock_get_vs.return_value = mock_vs

            retrieve_context("query")

            mock_vs.similarity_search.assert_called_once_with("query", k=2)

    def test_joins_multiple_documents_with_double_newline(self):
        from rag.retriever import retrieve_context

        with patch("rag.retriever.get_vectorstore") as mock_get_vs:
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [
                _mock_doc("doc one"),
                _mock_doc("doc two"),
            ]
            mock_get_vs.return_value = mock_vs

            result = retrieve_context("query")

        assert result == "doc one\n\ndoc two"

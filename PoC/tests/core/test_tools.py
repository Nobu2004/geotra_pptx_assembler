# tests/core/test_tools.py

import unittest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

from src.core import schemas

class TestMarkdownSearchTool(unittest.TestCase):
    # --- ★★★ 修正箇所 ★★★ ---
    # __init__メソッドをパッチして、モデルのダウンロードを完全に防ぐ
    @patch('src.core.tools.file_search.MarkdownSearchTool.__init__', return_value=None)
    def test_search_with_mock_data(self, mock_init):
        # 1. モック化されたインスタンスを作成
        from src.core.tools.file_search import MarkdownSearchTool
        tool = MarkdownSearchTool()

        # 2. 検索機能を持つベクトルストアをモックとしてインスタンスに設定
        mock_doc = Document(
            page_content="AIはプレゼンテーション作成を支援します。",
            metadata={"source": "internal_report.md"}
        )
        mock_vector_store = MagicMock()
        mock_vector_store.similarity_search.return_value = [mock_doc]
        tool.vector_store = mock_vector_store # モックを直接注入

        # 3. 検索の実行と検証
        query = "AIの役割"
        results = tool.search(query)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], schemas.ResearchFinding)
        self.assertEqual(results[0].content, "AIはプレゼンテーション作成を支援します。")
        
        mock_vector_store.similarity_search.assert_called_once_with(query, k=3)


class TestWebSearchTool(unittest.TestCase):
    # --- ★★★ 修正箇所 ★★★ ---
    # 正しいクラスパスをパッチ
    @patch('src.core.tools.web_search.TavilySearch')
    def test_search_with_mock_api(self, mock_tavily):
        mock_api_result = [{"url": "https://example.com/ai-trends", "content": "2025年のAIトレンドは生成AIのさらなる進化です。"}]
        mock_tavily.return_value.invoke.return_value = mock_api_result
        
        from src.core.tools.web_search import WebSearchTool
        tool = WebSearchTool()

        query = "2025年のAIトレンド"
        results = tool.search(query)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], schemas.ResearchFinding)
        self.assertEqual(results[0].content, "2025年のAIトレンドは生成AIのさらなる進化です。")
        self.assertEqual(results[0].source, "https://example.com/ai-trends")
        
        mock_tavily.return_value.invoke.assert_called_once_with(query)

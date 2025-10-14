# tests/core/test_graph.py

import unittest
from unittest.mock import patch
from src.core.graph import create_graph
from src.core import schemas

class TestAIGraph(unittest.TestCase):

    @patch('src.core.agents.researcher.markdown_search_tool.search')
    @patch('src.core.agents.researcher.web_search_tool.search')
    def test_full_graph_run(self, mock_web_search, mock_md_search):
        """
        グラフ全体が正常に実行され、期待されるStateの遷移が行われるかをテストする。
        """
        # --- 準備 (Arrange) ---
        # 外部ツールからの戻り値をモック化
        mock_md_search.return_value = [
            schemas.ResearchFinding(content="内部文書によると、AIは重要です。", source="internal_report.md")
        ]
        mock_web_search.return_value = [
            schemas.ResearchFinding(content="ウェブによると、AIの市場は拡大しています。", source="https://example.com")
        ]

        graph = create_graph()
        
        # 実行する入力データ
        initial_state = {
            "initial_user_request": "体制図についてAIを活用したスライドを作成して",
            "messages": [("user", "体制図についてAIを活用したスライドを作成して")]
        }

        # --- 実行 (Act) ---
        # グラフを実行し、最終的な状態を取得
        final_state = graph.invoke(initial_state)

        # --- 検証 (Assert) ---
        # 1. PMエージェントが正しく動作したか
        self.assertIn("slide_blueprints", final_state)
        self.assertEqual(len(final_state["slide_blueprints"]), 1)
        blueprint = final_state["slide_blueprints"][0]
        self.assertEqual(blueprint.asset_id, "org_chart_001") # "体制図"から正しく選択されたか

        # 2. リサーチャーエージェントが正しく動作したか
        self.assertIn("research_report", final_state)
        report = final_state["research_report"]
        self.assertEqual(len(report.findings), 2) # 内部文書とウェブの両方から取得

        # 3. ライターエージェントが(シミュレーションで)正しく動作したか
        # writer.pyのダミー応答に基づき、コンテンツが更新されているかを確認
        written_content = blueprint.content_map[1].content # 2番目のプレースホルダー
        self.assertIn("知的リサーチ・アシスタント", written_content)

        print("\n--- グラフテスト完了 ---")
        print("最終的なスライド設計図:")
        import pprint
        pprint.pprint(blueprint.model_dump())

if __name__ == '__main__':
    unittest.main()


# src/core/tools/web_search.py

import os
from typing import List
from dotenv import load_dotenv

from langchain_tavily import TavilySearch
from .. import schemas

load_dotenv()

class WebSearchTool:
    """
    Tavily Search APIを利用したウェブ検索ツール。
    """
    def __init__(self):
        """
        初期化時にAPIキーの存在を確認し、検索クライアントをセットアップする。
        """
        if not os.getenv("TAVILY_API_KEY"):
            raise ValueError(
                "環境変数 'TAVILY_API_KEY' が設定されていません。\n"
                "Tavily AI (https://tavily.com/) でAPIキーを取得し、\n"
                "プロジェクトルートの .env ファイルに TAVILY_API_KEY='...' と記述してください。"
            )
        
        self.client = TavilySearch(max_results=3)

    def search(self, query: str) -> List[schemas.ResearchFinding]:
        """
        指定されたクエリでウェブを検索し、結果を整形して返す。
        """
        print(f"'{query}' でウェブを検索中...")
        try:
            results = self.client.invoke(query)
            
            findings = []
            if isinstance(results, list):
                for result in results:
                    if "content" in result and "url" in result:
                        finding = schemas.ResearchFinding(
                            content=result["content"],
                            source=result["url"]
                        )
                        findings.append(finding)
            return findings
        except Exception as e:
            print(f"!!! ウェブ検索中にエラーが発生しました: {e}")
            return []

web_search_tool = WebSearchTool()

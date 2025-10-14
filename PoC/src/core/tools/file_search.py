# src/core/tools/file_search.py

from pathlib import Path
from typing import List

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from .. import schemas

ROOT_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
MD_DOCUMENT_PATH = DATA_DIR / "internal_report.md"
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"

class MarkdownSearchTool:
    """
    ローカルのMarkdownファイルを対象としたセマンティック検索ツール。
    RAGパイプラインをカプセル化する。
    """
    def __init__(self):
        """
        初期化時に、ドキュメントを読み込み、ベクトルストアを構築する。
        """
        print("--- MarkdownSearchToolを初期化中 ---")
        if not MD_DOCUMENT_PATH.exists():
            raise FileNotFoundError(f"リサーチ対象ドキュメント '{MD_DOCUMENT_PATH}' が見つかりません。")

        try:
            loader = UnstructuredMarkdownLoader(MD_DOCUMENT_PATH)
            docs = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", "。", "、", ""]
            )
            chunks = text_splitter.split_documents(docs)

            print(f"埋め込みモデル '{EMBEDDING_MODEL_NAME}' をロード中...")
            self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

            print("ベクトルストアを構築中...")
            self.vector_store = FAISS.from_documents(chunks, self.embeddings)
            print("--- MarkdownSearchToolの初期化完了 ---")

        except Exception as e:
            print(f"!!! MarkdownSearchToolの初期化中にエラーが発生しました: {e}")
            self.vector_store = None

    def search(self, query: str, top_k: int = 3) -> List[schemas.ResearchFinding]:
        """
        指定されたクエリでMarkdownドキュメント内を検索し、関連性の高い情報を返す。
        """
        if self.vector_store is None:
            print("エラー: ベクトルストアが初期化されていません。検索を実行できません。")
            return []
            
        print(f"'{query}' でドキュメント内を検索中...")
        try:
            relevant_docs = self.vector_store.similarity_search(query, k=top_k)
            
            findings = []
            for doc in relevant_docs:
                finding = schemas.ResearchFinding(
                    content=doc.page_content,
                    source=f"{MD_DOCUMENT_PATH.name} (関連箇所)"
                )
                findings.append(finding)
            
            return findings
        except Exception as e:
            print(f"!!! ドキュメント内検索中にエラーが発生しました: {e}")
            return []

markdown_search_tool = MarkdownSearchTool()

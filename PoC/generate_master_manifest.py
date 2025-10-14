# generate_master_manifest.py
# プロジェクトのルートディレクトリに配置して実行

import json
from pathlib import Path
from src.core import pptx_utils

# --- 設定 ---generate_master_manifest.py
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
TEMPLATE_DIR = ASSETS_DIR / "templates"
MASTER_TEMPLATE_PATH = TEMPLATE_DIR / "master_template.pptx"
OUTPUT_MANIFEST_PATH = TEMPLATE_DIR / "master_manifest.json"
# ---

def main():
    """
    マスターテンプレートを解析し、レイアウト情報をJSONとして出力する。
    """
    print("--- マスターテンプレートマニフェスト生成 ---")
    
    if not MASTER_TEMPLATE_PATH.exists():
        print(f"エラー: マスターテンプレート '{MASTER_TEMPLATE_PATH}' が見つかりません。")
        return

    print(f"'{MASTER_TEMPLATE_PATH}' からレイアウト情報を抽出しています...")
    layouts = pptx_utils.get_layouts_from_master(MASTER_TEMPLATE_PATH)
    
    if not layouts:
        print("レイアウト情報が抽出できませんでした。")
        return

    manifest_data = {
        "master_template_file": MASTER_TEMPLATE_PATH.name,
        "description": "プレゼンテーション全体のデザイン統一性を担保する基本レイアウト群。",
        "layouts": layouts
    }

    with open(OUTPUT_MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n[完了] レイアウト情報を '{OUTPUT_MANIFEST_PATH}' に保存しました。")
    print(f"検出されたレイアウト数: {len(layouts)}")
    for layout in layouts:
        print(f"  - {layout['layout_name']} (Index: {layout['layout_index']})")

if __name__ == "__main__":
    main()

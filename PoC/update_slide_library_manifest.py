# update_slide_library_manifest.py
# プロジェクトのルートディレクトリに配置して実行

import os
import json
from pathlib import Path
import re
import tempfile
import platform
import subprocess
from src.core import pptx_utils

# --- 設定 ---
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
SLIDE_LIBRARY_DIR = ASSETS_DIR / "slide_library"
MANIFEST_PATH = SLIDE_LIBRARY_DIR / "slide_library_manifest.json"
# ---

def load_manifest():
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"slide_assets": []}
    return {"slide_assets": []}

def save_manifest(data):
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_unique_id(base_name, existing_ids):
    base_name = re.sub(r'[^\w\s-]', '', base_name.lower())
    base_name = re.sub(r'[-\s]+', '_', base_name).strip('_')
    i = 1
    while True:
        new_id = f"{base_name}_{i:03d}"
        if new_id not in existing_ids:
            return new_id
        i += 1

def get_edit_policy_from_user():
    policies = {'1': 'generate', '2': 'populate', '3': 'fixed'}
    while True:
        print("  [1] generate: AIが内容を完全に自動生成")
        print("  [2] populate: システム情報（日付など）を自動入力")
        print("  [3] fixed:    テンプレートのテキストをそのまま固定")
        choice = input("  ▶︎ 編集ポリシーを選択してください (1/2/3): ")
        if choice in policies:
            return policies[choice]
        print("  [エラー] 1, 2, 3のいずれかを入力してください。")

def main():
    print("--- サンプルスライドマニフェスト更新 ---")
    manifest_data = load_manifest()
    
    slide_assets = manifest_data.get("slide_assets", [])
    processed_files = {asset['file_name'] for asset in slide_assets}
    existing_ids = {asset['id'] for asset in slide_assets}

    new_files_found = False
    for filename in os.listdir(SLIDE_LIBRARY_DIR):
        if filename.endswith(".pptx") and filename not in processed_files:
            new_files_found = True
            print(f"\n[新規ファイル検出] '{filename}' の情報を登録します。")
            
            pptx_path = SLIDE_LIBRARY_DIR / filename
            placeholders_info = pptx_utils.get_placeholders_from_slide(pptx_path)
            if not placeholders_info:
                print(f"警告: '{filename}' からプレースホルダーが検出されませんでした。スキップします。")
                continue

            with tempfile.TemporaryDirectory() as temp_dir:
                preview_image_path = Path(temp_dir) / "preview.png"
                print("注釈付きプレビューを生成しています...")
                success = pptx_utils.create_annotated_preview(pptx_path, preview_image_path)
                
                if success:
                    print(f"\n[確認] 注釈付きプレビューを '{preview_image_path}' に生成しました。")
                    if platform.system() == "Darwin":
                        subprocess.run(["open", str(preview_image_path)])
                else:
                    print("\n[警告] プレビュー画像が生成できませんでした。プレースホルダー名の一覧を参考にしてください。")
                    for ph in placeholders_info:
                        print(f"  - {ph['name']} (Index: {ph['idx']})")

                description = input("▶︎ このスライドの説明: ")
                category = input("▶︎ カテゴリ (例: 図解, 分析フレームワーク): ")
                tags_str = input("▶︎ タグ (カンマ区切り, 例: 組織図, 体制図): ")
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

                print("\n--- ▼ プレースホルダーの目的と編集ポリシーを入力してください ---")
                placeholders_for_manifest = []
                for ph_info in placeholders_info:
                    ph_name = ph_info['name']
                    ph_idx = ph_info['idx']
                    print(f"\n--- プレースホルダー: '{ph_name}' (Index: {ph_idx}) ---")
                    ph_desc = input(f"▶︎ '{ph_name}' の目的: ")
                    ph_policy = get_edit_policy_from_user()
                    placeholders_for_manifest.append({
                        "name": ph_name,
                        "idx": ph_idx, # ★★★ インデックスを保存 ★★★
                        "description": ph_desc,
                        "edit_policy": ph_policy
                    })
                print("--- ▲ 入力ありがとうございました ---")

            base_id_name = Path(filename).stem
            new_id = generate_unique_id(base_id_name, existing_ids)
            new_asset = {
                "id": new_id,
                "file_name": filename,
                "description": description,
                "category": category,
                "tags": tags,
                "placeholders": placeholders_for_manifest
            }
            
            slide_assets.append(new_asset)
            existing_ids.add(new_id)
            print(f"\n ✓ '{filename}' の情報がマニフェストに追加されました。")

    if not new_files_found:
        print("\n新しいスライド資産は見つかりませんでした。マニフェストは最新の状態です。")
        return

    manifest_data["slide_assets"] = slide_assets
    save_manifest(manifest_data)
    print(f"\n[完了] マニフェストファイル '{MANIFEST_PATH}' が更新されました。")

if __name__ == "__main__":
    main()

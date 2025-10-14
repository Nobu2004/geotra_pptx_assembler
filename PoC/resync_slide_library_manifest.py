# resync_slide_library_manifest.py
# プロジェクトのルートディレクトリに配置して実行
# 既存のslide_library_manifest.jsonを読み込み、
# 各サンプルスライド(.pptx)の現在の状態を「正」として、
# プレースホルダー情報（name, idx）を更新する。
# 既存のdescriptionやedit_policyは可能な限り保持する。

import json
import shutil
from pathlib import Path
from src.core import pptx_utils

# --- 設定 ---
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
SLIDE_LIBRARY_DIR = ASSETS_DIR / "slide_library"
MANIFEST_PATH = SLIDE_LIBRARY_DIR / "slide_library_manifest.json"
BACKUP_PATH = SLIDE_LIBRARY_DIR / "slide_library_manifest.json.bak"
# ---

def resync_manifest():
    """
    slide_library_manifest.jsonと実際のPPTXファイルの状態を同期させる。
    """
    print("--- slide_library_manifest.json 緊急同期スクリプト ---")

    if not MANIFEST_PATH.exists():
        print(f"[エラー] マニフェストファイル '{MANIFEST_PATH}' が見つかりません。")
        return

    # 1. 安全のために元のマニフェストをバックアップ
    print(f"元のマニフェストを '{BACKUP_PATH}' にバックアップしています...")
    shutil.copy2(MANIFEST_PATH, BACKUP_PATH)
    print(" ✓ バックアップが完了しました。")

    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)

    assets = manifest_data.get("slide_assets", [])
    
    print("\n--- マニフェストとPPTXファイルの同期を開始します ---")
    for asset in assets:
        file_name = asset.get("file_name")
        asset_id = asset.get("id")
        print(f"\n[処理中] アセットID: '{asset_id}' (ファイル: '{file_name}')")

        if not file_name:
            print("  [警告] file_nameが定義されていません。スキップします。")
            continue

        pptx_path = SLIDE_LIBRARY_DIR / file_name
        if not pptx_path.exists():
            print(f"  [警告] 対応するPPTXファイル '{pptx_path}' が見つかりません。スキップします。")
            continue

        # 2. PPTXファイルから現在のプレースホルダー情報（= 正）を取得
        placeholders_from_pptx = pptx_utils.get_placeholders_from_slide(pptx_path)
        
        # 3. 既存のdescriptionとedit_policyを保持するためのマップを作成
        old_placeholders_map = {
            ph.get("name"): {
                "description": ph.get("description", "（説明を追記してください）"),
                "edit_policy": ph.get("edit_policy", "generate")
            }
            for ph in asset.get("placeholders", [])
        }

        # 4. 新しいプレースホルダーリストを構築
        new_placeholders_list = []
        for ph_from_pptx in placeholders_from_pptx:
            current_name = ph_from_pptx["name"]
            current_idx = ph_from_pptx["idx"]
            
            # 既存の情報を引き継ぐ
            old_info = old_placeholders_map.get(current_name)
            if old_info:
                description = old_info["description"]
                edit_policy = old_info["edit_policy"]
            else:
                # PPTXには存在するが、マニフェストになかった新しいプレースホルダー
                print(f"  [新規検出] プレースホルダー '{current_name}' (idx: {current_idx}) を追加します。")
                description = "（AIへの指示を記述してください）"
                edit_policy = "generate" # デフォルトはgenerate

            new_placeholders_list.append({
                "name": current_name,
                "idx": current_idx,
                "description": description,
                "edit_policy": edit_policy
            })
        
        # 5. アセットのプレースホルダー情報を更新
        asset["placeholders"] = new_placeholders_list
        print(f"  ✓ '{file_name}' のプレースホルダー情報を更新しました。")

    # 6. 更新された内容でマニフェストを上書き保存
    print("\n--- 同期処理完了 ---")
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    
    print(f"[完了] マニフェストファイル '{MANIFEST_PATH}' が更新されました。")
    print("git diff等で変更内容を確認し、問題なければテストを再実行してください。")


if __name__ == "__main__":
    resync_manifest()

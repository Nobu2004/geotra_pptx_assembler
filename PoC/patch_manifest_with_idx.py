# patch_manifest_with_idx.py
# プロジェクトのルートディレクトリに配置して実行
# 既存のマニフェスト情報を保持しつつ、PowerPointファイルからidxを抽出し、不足している場合のみ追加する。

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

def patch_manifest():
    """
    slide_library_manifest.jsonを読み込み、
    各アセットのプレースホルダーに'idx'キーがなければ、
    対応する.pptxファイルから情報を補完して上書き保存する。
    """
    print("--- 緊急マニフェストパッチスクリプト ---")

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
    patched_assets_count = 0
    
    print("\n--- マニフェストのチェックとパッチを開始します ---")
    for asset in assets:
        file_name = asset.get("file_name")
        placeholders = asset.get("placeholders", [])

        if not file_name or not placeholders:
            continue

        # プレースホルダーのいずれかに 'idx' がなければパッチ対象と判断
        if any('idx' not in ph for ph in placeholders):
            print(f"\n[パッチ対象] '{file_name}' のプレースホルダー情報を更新します。")
            patched_assets_count += 1
            
            pptx_path = SLIDE_LIBRARY_DIR / file_name
            if not pptx_path.exists():
                print(f"  [警告] 対応するPPTXファイル '{pptx_path}' が見つかりません。スキップします。")
                continue

            # PowerPointファイル自体を「正」として、プレースホルダー情報を抽出
            placeholders_from_pptx = pptx_utils.get_placeholders_from_slide(pptx_path)
            if not placeholders_from_pptx:
                print(f"  [警告] '{file_name}' からプレースホルダーが検出できませんでした。")
                continue
            
            # 高速なルックアップのために、名前をキーとする辞書を作成
            name_to_idx_map = {ph['name']: ph['idx'] for ph in placeholders_from_pptx}

            # 既存のプレースホルダー定義に 'idx' を追加
            for manifest_ph in placeholders:
                ph_name = manifest_ph.get("name")
                if ph_name in name_to_idx_map:
                    manifest_ph['idx'] = name_to_idx_map[ph_name]
                else:
                    print(f"  [警告] マニフェスト上のプレースホルダー '{ph_name}' が、現在のPPTXファイル内に見つかりません。")
    
    if patched_assets_count == 0:
        print("\nすべてのマニフェストは最新の状態です。パッチは不要でした。")
        # 不要ならバックアップファイルを削除
        BACKUP_PATH.unlink()
        print(f"バックアップファイル '{BACKUP_PATH}' を削除しました。")
        return

    # 3. 更新された内容でマニフェストを上書き保存
    print(f"\n--- パッチ処理完了。{patched_assets_count}件のアセットを更新しました ---")
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    
    print(f"[完了] マニフェストファイル '{MANIFEST_PATH}' が更新されました。")


if __name__ == "__main__":
    patch_manifest()
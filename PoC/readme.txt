manifest.jsonの全体像
私たちは、プレゼンテーション資産を以下の2種類に大別し、それぞれに対応するマニフェストファイルを用意します。

マスターテンプレート (master_template.pptx):

プレゼンテーション全体のデザイン（フォント、色、ロゴなど）を規定する「法律」です。

これに対応するのが master_manifest.json です。

サンプルスライド (slide_library/内の各.pptx):

特定の目的を持つ、再利用可能な「部品」です。（例：組織図、SWOT分析フレームワーク）

これに対応するのが slide_library_manifest.json です。

1. master_manifest.json
目的
このファイルは、マスターテンプレート内に定義されている**全レイアウトの「カタログ」**として機能します。AIが「ゼロから新しいスライドを作成する (generatedタイプ)」際に、どのような種類のレイアウト（設計図）が利用可能かを知るために参照します。

形式と情報
generate_master_manifest.pyによって自動生成される、レイアウトの一覧です。

// assets/templates/master_manifest.json
{
  "master_template_file": "master_template.pptx",
  "description": "プレゼンテーション全体のデザイン統一性を担保する基本レイアウト群。",
  "layouts": [
    {
      "layout_index": 15,
      "layout_name": "内容_1コラム_A",
      "placeholders": [
        {
          "name": "タイトル プレースホルダー 1",
          "type": "TITLE (1)",
          "idx": 0
        },
        {
          "name": "コンテンツ プレースホルダー 2",
          "type": "OBJECT (7)",
          "idx": 1
        }
      ]
    }
    // ... 他のレイアウト情報が続く
  ]
}

各情報の意味
master_template_file: このマニフェストがどのファイルに対応するかを示します。

description: このマニフェスト全体の目的を示す、人間向けの説明です。

layouts: 利用可能な全レイアウトのリストです。

layout_index: python-pptxがレイアウトを適用する際に使用する内部的な番号です。

layout_name: 人間が識別するためのレイアウト名です。（例：「内容_1コラム_A」）

placeholders: そのレイアウトに含まれるプレースホルダー（入力欄）の一覧です。

name: PowerPoint内で付けられた名前。（例：「タイトル プレースホルダー 1」）

type, idx: プレースホルダーの種類やインデックスといった、プログラムが利用する詳細情報です。

2. slide_library_manifest.json
目的
このファイルは、slide_library/に格納されている各サンプルスライドの詳細な「取扱説明書」として機能します。AIがユーザーの指示を解釈し、「どの部品（サンプルスライド）が今回のタスクに最適か」「その部品のどこに何を書くべきか」を知的に判断するために参照します。

形式と情報
update_slide_library_manifest.pyを使い、自動抽出と人間との対話によって生成されます。

// assets/slide_library/slide_library_manifest.json
{
  "slide_assets": [
    {
      "id": "org_chart_001",
      "file_name": "organization_chart.pptx",
      "description": "部門やチームの階層構造を示すための組織図。上位の役職者と複数の部下を表現するのに適している。",
      "category": "図解",
      "tags": ["組織図", "体制図", "チーム構造"],
      "placeholders": [
        {
          "name": "TopBox_Name",
          "description": "最上位の役職者の氏名を記述します。",
          "edit_policy": "generate"
        },
        {
          "name": "Date Placeholder",
          "description": "システムが現在の日付を自動入力します。元のテキストは {{CURRENT_DATE}} のように指定します。",
          "edit_policy": "populate"
        },
        {
          "name": "Title Placeholder",
          "description": "スライドのタイトルです。元のテキスト『アジェンダ』をそのまま使用します。",
          "edit_policy": "fixed"
        }
      ]
    }
    // ... 他のサンプルスライドの情報が続く
  ]
}

各情報の意味
id: システムが各スライド資産を一意に識別するためのIDです。

file_name: 対応する.pptxファイル名です。

description: 【AIにとって最も重要】 このスライドが何のためのものか、どのような状況で役立つかを自然言語で説明します。AIはこれを読んで、ユーザーの意図に合致するかを判断します。

category, tags: 【AIの検索能力を向上】 AIが多数の資産の中から適切なものを絞り込むための検索キーです。「分析フレームワーク」というカテゴリで探し、「SWOT」というタグでさらに絞り込む、といった使い方をします。

placeholders: 【AIの知的活用の核】

name: PowerPoint内のプレースホルダー名です。

description: 【AIへの具体的な指示】 このプレースホルダーにどのような内容を生成して入れるべきかをAIに教える、最も重要な指示書です。「強み(Strength)を箇条書きで記述します」といった具体的な指示があることで、AIは高品質なコンテンツを適切な場所に生成できます。

edit_policy: 【AIの振る舞いを制御（更新）】 このプレースホルダーの内容をAIがどのように扱うべきかを示す編集ポリシーです。以下のいずれかの値を設定します。

generate: AIによる完全自動生成。 リサーチ結果や文脈に基づき、AIが内容を自由に生成・編集します。（例：分析結果、要約、箇条書きの本文）

populate: システム情報からの自動入力。 サンプルスライド内の特定の値（例：{{CURRENT_DATE}}, {{PROJECT_NAME}}）を、システムが実行時に自動で入力します。AIはこのプレースホルダーの内容を生成しません。

fixed: テンプレートのまま固定。 サンプルスライドに書かれているテキストを一切変更せずにそのまま使用します。（例：「アジェンダ」という見出しそのもの、コピーライト表記、固定の注意書き）

まとめ
観点

master_manifest.json

slide_library_manifest.json

目的

デザインのカタログ

再利用部品の取扱説明書

対象

master_template.pptx 1つ

slide_library/内の多数の.pptx

AIの主な利用方法

ゼロからスライドを作る際の設計図を選ぶ

最適な部品を探し、その使い方と変更ルールを理解する

更新頻度

マスターテンプレート変更時に一括更新

新しいサンプルスライド追加時に追記

この2つのマニフェストを明確に分離・設計することで、システムの安定性と拡張性を両立させ、AIが真に「アシスタント」として機能するための基盤を構築します。
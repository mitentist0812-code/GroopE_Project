# GroopE_Project
卒業制作Eチーム

## アプリの起動

プロジェクトの仮想環境を有効にして、次のコマンドでFlaskアプリを起動します。

```powershell
flask --app apps:create_app run --debug
```

## アプリ構成

- `apps/auth`: ログインと会員登録
- `apps/home`: ホームと検索結果
- `apps/recipes`: レシピ
- `apps/users`: マイページ、設定、お気に入り、履歴
- `apps/restaurants`: 店舗、メニュー、予約
- `apps/nutrition`: カロリー計算
- `apps/templates/shared`: 共通レイアウト

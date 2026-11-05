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

## GitHubへのプッシュ

チームで作業するときは、`main`へ直接プッシュせず、作業用ブランチからPull Requestを作成してください。

### 作業を始めるとき

下のブロックをコピーして実行します。ブランチ名は例として`feature/my-change`を使っています。同じ名前のブランチをすでに作成している場合は、`git switch -c`の代わりに`git switch feature/my-change`を実行してください。

```powershell
git switch main
git pull origin main
git switch -c feature/my-change
```

### 変更をプッシュするとき

変更したファイルを確認してから、次のブロックを実行します。コミットメッセージは今回の変更内容に合わせて書き換えてください。

```powershell
git status
git add .
git commit -m "Update project files"
git push -u origin feature/my-change
```

初回のプッシュ後、GitHubで`feature/my-change`からPull Requestを作成し、レビュー後に`main`へ取り込みます。同じブランチに追加で変更した場合は、次のコマンドを実行します。

```powershell
git status
git add .
git commit -m "Update project files"
git push
```

`.env`や`venv`はGitの対象外です。`.env`には秘密情報を含めないようにし、プッシュしないでください。

不明なことがある場合各自調べてください

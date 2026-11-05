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

# GitHubへのプッシュ手順

このリポジトリで開発するときは、以下の手順に従ってください。

## 1. リポジトリをクローンする（初回のみ）

```powershell
git clone https://github.com/mitentist0812-code/GroopE_Project.git
cd GroopE_Project
```

## 2. 最新のmainブランチを取得する

作業を始める前に、`main`ブランチの最新状態を取得します。

```powershell
git switch main
git pull origin main
```

## 3. 作業用ブランチを作成する

`main`ブランチに直接変更を加えず、作業内容に応じたブランチを作成します。

```powershell
git switch -c feature/login
```

ブランチ名の例：

- `feature/`: 新機能の追加（例：`feature/search`）
- `fix/`: バグの修正（例：`fix/login-error`）
- `design/`: デザインの変更（例：`design/header`）

## 4. ファイルを編集する

VS Codeなどで担当箇所を編集し、変更内容を確認します。

```powershell
git status
```

## 5. 変更をコミットする

```powershell
git add .
git commit -m "ログイン画面を作成"
```

コミットメッセージは、実際の変更内容に合わせてください。

## 6. GitHubにプッシュする

作成した作業用ブランチをGitHubにアップロードします。

```powershell
git push -u origin feature/login
```

同じブランチに追加の変更をプッシュする場合は、変更をコミットした後に次のコマンドを実行します。

```powershell
git push
```

## 7. Pull Requestを作成する

プッシュ後、GitHubでリポジトリを開き、作業用ブランチからPull Requestを作成します。

1. 「Compare & pull request」を選択します。
2. `base`が`main`になっていることを確認します。
3. 変更内容を記入します。
4. 「Create pull request」を選択します。

Pull Requestは、管理者または他のメンバーによる確認後に`main`へマージします。

## 8. 次回以降の作業

作業を始めるたびに、最新の`main`を取得してから新しい作業用ブランチを作成します。ブランチ名は作業に合わせて変更してください。

```powershell
git switch main
git pull origin main
git switch -c feature/search
```

## 開発時の注意事項

- `main`ブランチへ直接プッシュしないでください。
- 必ず作業用ブランチを作成してください。
- 作業開始前に`main`ブランチを最新の状態にしてください。
- コミットメッセージには変更内容を簡潔に記述してください。
- `main`への反映はPull Requestを通してください。
- `.env`など、パスワードや秘密情報を含むファイルはプッシュしないでください。

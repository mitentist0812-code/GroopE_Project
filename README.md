# GroopE_Project

卒業制作Eチーム

## アプリの起動

プロジェクトの仮想環境とOllamaを準備した後、リポジトリ直下の`run.bat`をダブルクリックするとFlaskアプリを起動できます。バッチファイルはOllamaの稼働とモデルを確認し、停止中の場合はOllamaを最小化した別ウィンドウで起動してから、プロジェクト内の`venv`を使用して`apps:create_app`を起動します。Ollamaはアプリ終了後も稼働します。起動時にOllamaやモデルが見つからない場合は、表示された案内に従ってください。

コマンドから起動する場合は、仮想環境を有効にして次を実行します。

```powershell
flask --app apps:create_app run --debug
```

## 気分に合わせたAIの料理提案

気分検索では、気分と料理ジャンルをローカルのOllamaに送り、提案された料理ごとにGoogle Places APIで店舗を検索します。予算や現在地はAIには送りません。ブラウザで現在地を許可する必要があり、現在地はGoogle Places APIの検索に使われます。検索は現在地から5kmの範囲を優先しますが、範囲外の店舗が含まれる場合があります。

1. [Ollama](https://ollama.com/)をインストールします。手動でFlaskを起動する場合はOllamaも起動してください。
2. PowerShellで `ollama pull llama3.1` を実行してモデルを取得します。
3. Google Cloudで課金を設定し、Places API (New) を有効にしてAPIキーを作成します。キーはPlaces APIに制限し、サーバーからのリクエストに適した制限を設定してください。料金はGoogleの料金表をご確認ください。
4. アプリ起動前にPowerShellで `$env:GOOGLE_MAPS_API_KEY = "取得したAPIキー"` を設定します。APIキーをソースコードやGitに登録しないでください。
5. 同じPowerShellで `.\run.bat` を実行し、「気分検索」に入力して検索し、位置情報を許可します。ブラウザの位置情報にはlocalhostまたはHTTPSが必要です。

OllamaのAPIは `127.0.0.1:11434` を使用します。別のインストール済みモデルを使う場合は、アプリの起動前にPowerShellで `$env:OLLAMA_MODEL = "モデル名"` を設定してください。初回の応答には時間がかかる場合があります。

予算を入力すると、Googleの価格帯で大まかに絞り込みます。アプリ独自の目安として、1,000円未満は「安め」、1,000円以上は「普通」まで、3,000円以上は「高め」まで、10,000円以上は「非常に高い」までを対象とします。価格帯は料理の実際の値段ではなく、予算内で食べられる保証はありません。価格帯が未登録の店舗は結果から除外される場合があります。予算未入力時は価格帯で絞り込みません。料理3件それぞれにPlaces APIを呼び出すため、1回の検索で最大3回のAPI利用が発生します。

気分検索の店舗一覧はGoogle Mapsのデータです。レシピ一覧、およびフリー検索・直接表示の店舗一覧はサンプルであり、検索条件による絞り込みは行いません。

気分検索の「店舗詳細」は選択した店舗の情報と写真をPlaces APIから取得します。写真が登録されていない場合はNoImage画像を表示し、写真取得時のエラーは画面に表示します。詳細表示ごとにPlace Details (New) および写真取得の利用料金が発生する場合があります。紹介文、アクセス情報および実店舗の予約・お気に入り・レビュー機能は未対応です。検索結果への戻りはブラウザの履歴を使用し、履歴の状態によってはフォームの再送信確認が表示されます。

## アプリ構成

- `apps/auth`: ログインと会員登録
- `apps/home`: ホームと検索結果
- `apps/recipes`: レシピ
- `apps/users`: マイページ、設定、お気に入り、履歴
- `apps/restaurants`: 店舗、メニュー、予約
- `apps/nutrition`: カロリー計算
- `apps/templates/shared`: 共通レイアウト
- `apps/static`: CSS（`css`）、画像（`img`）、JavaScript（`js`）

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

リポジトリ直下の`start-work-branch.bat`を実行すると、最新の`main`を取得して作業用ブランチを作成できます。`feature`（新機能）、`fix`（バグ修正）、`design`（デザイン変更）を選び、ブランチ名を入力してください。たとえば`feature`と`search`を選ぶと`feature/search`が作成されます。

コマンドで行う場合は、次のように実行します。ブランチ名は作業内容に合わせて変更してください。

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

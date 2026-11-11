
# SQLAlchemyをインポートする
# データベースの作成や、データの登録・取得・削除などを行うために使用する
from flask_sqlalchemy import SQLAlchemy

# 日時を扱うためのdatetimeをインポートする
# レシピの投稿日や閲覧日時などを記録するために使用する
from datetime import datetime


# SQLAlchemyのインスタンスを作成する
# このdbを使って、各テーブル（クラス）を定義する
# app.py側でdb.init_app(app)を実行してFlaskと接続する
db = SQLAlchemy()


# ============================================
# ユーザー情報テーブル
# ============================================
# アプリを利用するユーザーの情報を管理するテーブル
# ユーザーの識別や、お気に入り・レビューの投稿者を確認するために使用する
class User(db.Model):

    # データベース上で使用するテーブル名を指定する
    __tablename__ = "user"

    # ユーザーを識別するためのID
    # Integer：整数型
    # primary_key=True：主キーに設定し、ユーザーごとに異なるIDを付ける
    # データを登録するとIDは自動的に設定される
    id = db.Column(db.Integer, primary_key=True)

    # ユーザー名を保存するカラム
    # String(100)：最大100文字の文字列
    # unique=True：同じユーザー名を重複して登録できないようにする
    # nullable=False：空の値（NULL）を登録できないようにする
    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )


# ============================================
# レシピ情報テーブル
# ============================================
# ユーザーが投稿したレシピの情報を管理するテーブル
# レシピ名・材料・作り方・投稿日時を保存する
class Recipe_list(db.Model):

    # データベース上で使用するテーブル名を指定する
    __tablename__ = "recipe_list"

    # レシピを識別するためのID
    # 主キーとして設定し、レシピごとに異なるIDを付ける
    id = db.Column(db.Integer, primary_key=True)

    # レシピの名前を保存するカラム
    # String(100)：最大100文字の文字列
    # nullable=False：レシピ名の入力を必須にする
    recipe_name = db.Column(
        db.String(100),
        nullable=False
    )

    # レシピに使用する材料を保存するカラム
    # Text：長い文章を保存できる文字列型
    # 材料の種類や分量などを記録する
    # nullable=False：材料の入力を必須にする
    ingredients = db.Column(
        db.Text,
        nullable=False
    )

    # レシピの作り方を保存するカラム
    # Text：複数の手順など、長い文章を保存できる
    # nullable=False：作り方の入力を必須にする
    description = db.Column(
        db.Text,
        nullable=False
    )

    # レシピが投稿された日時を保存するカラム
    # DateTime：日付と時刻を保存する型
    # default=datetime.now：登録時に現在の日時を自動設定する
    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )


# ============================================
# レシピ閲覧履歴テーブル
# ============================================
# ユーザーがどのレシピを閲覧したかを管理するテーブル
# レシピ詳細画面を開いたときに閲覧履歴を保存するために使用する
class Search_history(db.Model):

    # データベース上で使用するテーブル名を指定する
    __tablename__ = "search_history"

    # 閲覧履歴を識別するためのID
    # 主キーとして設定し、履歴ごとに異なるIDを付ける
    id = db.Column(db.Integer, primary_key=True)

    # 閲覧したユーザーのIDを保存するカラム
    # ForeignKey("user.id")：Userテーブルのidと関連付ける
    # nullable=True：ログインしていないユーザーの閲覧も記録できるようにする
    # 未ログインの場合はNULLになる
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    # 閲覧したレシピのIDを保存するカラム
    # ForeignKey("recipe_list.id")：
    # Recipe_listテーブルのidと関連付ける
    # どのレシピが閲覧されたかを識別するために使用する
    # nullable=False：閲覧したレシピのIDは必須
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    # レシピを閲覧した日時を保存するカラム
    # DateTime：日付と時刻を保存する型
    # default=datetime.now：履歴を登録したときの日時を自動設定する
    viewed_at = db.Column(
        db.DateTime,
        default=datetime.now
    )


# ============================================
# お気に入り情報テーブル
# ============================================
# ユーザーがお気に入りに登録したレシピを管理するテーブル
# お気に入り登録やお気に入り解除を行うときに使用する
class Favorite(db.Model):

    # データベース上で使用するテーブル名を指定する
    __tablename__ = "favorite"

    # お気に入り情報を識別するためのID
    # 主キーとして設定し、登録ごとに異なるIDを付ける
    id = db.Column(db.Integer, primary_key=True)

    # お気に入り登録を行ったユーザーのID
    # ForeignKey("user.id")：Userテーブルのidと関連付ける
    # nullable=False：誰がお気に入り登録したかを必ず記録する
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # お気に入りに登録されたレシピのID
    # ForeignKey("recipe_list.id")：Recipe_listテーブルのidと関連付ける
    # nullable=False：対象のレシピを必ず指定する
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    # テーブルに対する制約を設定する
    # 同じユーザーが同じレシピを複数回お気に入り登録することを防ぐ
    # user_idとrecipe_idの組み合わせを重複不可にする
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "recipe_id",
            name="unique_favorite"
        ),
    )


# ============================================
# レビュー情報テーブル
# ============================================
# ユーザーが投稿したレシピのレビューを管理するテーブル
# 星評価とコメントを保存し、レシピ詳細画面に表示するために使用する
class Review(db.Model):

    # データベース上で使用するテーブル名を指定する
    __tablename__ = "review"

    # レビューを識別するためのID
    # 主キーとして設定し、レビューごとに異なるIDを付ける
    id = db.Column(db.Integer, primary_key=True)

    # レビューを投稿したユーザーのID
    # ForeignKey("user.id")：Userテーブルのidと関連付ける
    # 誰がレビューを投稿したかを識別するために使用する
    # nullable=False：投稿者のIDは必須
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # レビュー対象となるレシピのID
    # ForeignKey("recipe_list.id")：Recipe_listテーブルのidと関連付ける
    # どのレシピに対するレビューなのかを識別する
    # nullable=False：対象のレシピの指定を必須にする
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    # レシピに対する星評価を保存するカラム
    # Integer：整数型
    # 1～5の数字を保存し、星の数として表示する
    # nullable=False：星評価の入力を必須にする
    # ※1～5の範囲チェックは投稿処理側で行う
    rating = db.Column(
        db.Integer,
        nullable=False
    )

    # レビューのコメントを保存するカラム
    # Text：長い文章を保存できる文字列型
    # レシピを実際に作った感想などを記録する
    # nullable=False：コメントの入力を必須にする
    comment = db.Column(
        db.Text,
        nullable=False
    )

    # レビューが投稿された日時を保存するカラム
    # DateTime：日付と時刻を保存する型
    # default=datetime.now：レビュー登録時の日時を自動設定する
    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

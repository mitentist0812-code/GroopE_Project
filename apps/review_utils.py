from flask import current_app, session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from apps.auth.models import Account
from apps.extensions import db
from apps.review_models import ContentReview


def current_reviewer():
    email = session.get("email")
    if not email:
        return None
    return Account.query.filter_by(email=email, account_type="user").first()


def load_reviews(
    recipe_id=None,
    place_id=None,
    reviewer=None,
    sort="newest",
):
    if (recipe_id is None) == (place_id is None):
        raise ValueError("レビュー対象はレシピまたは店舗のどちらか一方にしてください。")

    query = ContentReview.query.options(joinedload(ContentReview.account))
    if recipe_id is not None:
        query = query.filter_by(recipe_id=recipe_id)
    else:
        query = query.filter_by(place_id=place_id)

    ordering = {
        "rating-desc": (
            ContentReview.rating.desc(),
            ContentReview.created_at.desc(),
        ),
        "rating-asc": (
            ContentReview.rating.asc(),
            ContentReview.created_at.desc(),
        ),
        "oldest": (ContentReview.created_at.asc(), ContentReview.id.asc()),
        "newest": (ContentReview.created_at.desc(), ContentReview.id.desc()),
    }.get(
        sort,
        (ContentReview.created_at.desc(), ContentReview.id.desc()),
    )
    reviews = query.order_by(*ordering).all()
    average = (
        sum(review.rating for review in reviews) / len(reviews)
        if reviews else None
    )
    own_review = next(
        (
            review for review in reviews
            if reviewer and review.account_id == reviewer.id
        ),
        None,
    )
    return reviews, average, own_review


def save_review(account, *, rating, comment, recipe_id=None, place_id=None):
    review = ContentReview.query.filter_by(
        account_id=account.id,
        recipe_id=recipe_id,
        place_id=place_id,
    ).first()
    if review is None:
        review = ContentReview(
            account_id=account.id,
            recipe_id=recipe_id,
            place_id=place_id,
        )
        db.session.add(review)
    review.rating = rating
    review.comment = comment
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("レビューの保存に失敗しました")
        return False
    return True


def save_review_form(account, form, *, recipe_id=None, place_id=None):
    if account is None:
        return "レビューを投稿するにはログインしてください。"
    if account.account_type != "user":
        return "レビューを投稿できるのは一般ユーザーのみです。"

    rating_value = form.get("rating", "")
    if rating_value not in ("1", "2", "3", "4", "5"):
        return "評価を1〜5の範囲で選択してください。"
    comment = form.get("comment", "").strip()
    if not comment or len(comment) > 1000:
        return "レビューは1〜1000文字で入力してください。"
    if not save_review(
        account,
        rating=int(rating_value),
        comment=comment,
        recipe_id=recipe_id,
        place_id=place_id,
    ):
        return "レビューを保存できませんでした。時間をおいて再度お試しください。"
    return None

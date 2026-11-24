from functools import lru_cache
from pathlib import Path
from typing import Any, List, Sequence, Tuple


MODEL_DIRECTORY = Path(__file__).resolve().parents[1] / "14-allergens-0.3b"
ALLERGEN_THRESHOLD = 0.5
MAX_TEXT_CHARACTERS = 8000
MAX_BATCH_SIZE = 16

ALLERGEN_NAMES_JA = {
    "celery": "セロリ",
    "crustaceans": "甲殻類",
    "eggs": "卵",
    "fish": "魚",
    "gluten": "小麦・グルテン",
    "lupin": "ルピナス",
    "milk": "乳",
    "mollusks": "軟体動物",
    "mustard": "マスタード",
    "nuts": "ナッツ類",
    "peanuts": "落花生",
    "sesame": "ごま",
    "soy": "大豆",
    "sulfites": "亜硫酸塩",
}


class AllergenModelUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_model() -> Tuple[Any, Any, Any]:
    if not MODEL_DIRECTORY.is_dir():
        raise AllergenModelUnavailable("ローカルのアレルゲンモデルが見つかりません。")

    try:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
    except ImportError as error:
        raise AllergenModelUnavailable(
            "アレルゲン判定に必要なPythonパッケージがありません。"
        ) from error

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_DIRECTORY,
            local_files_only=True,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_DIRECTORY,
            local_files_only=True,
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise AllergenModelUnavailable(
            "ローカルのアレルゲンモデルを読み込めませんでした。"
        ) from error

    model.eval()
    return torch, tokenizer, model


def _possible_allergens(
    labels: Sequence[str],
    scores: Sequence[float],
) -> List[str]:
    return [
        ALLERGEN_NAMES_JA[label]
        for label, score in zip(labels, scores)
        if label in ALLERGEN_NAMES_JA and score >= ALLERGEN_THRESHOLD
    ]


def analyze_allergens(texts: Sequence[str]) -> List[List[str]]:
    results = [[] for _ in texts]
    text_indexes = [
        index for index, text in enumerate(texts)
        if isinstance(text, str) and text.strip()
    ]
    if not text_indexes:
        return results

    torch, tokenizer, model = _load_model()
    id_to_label = model.config.id2label
    labels = [
        id_to_label[index] if index in id_to_label else id_to_label[str(index)]
        for index in range(len(id_to_label))
    ]

    try:
        for batch_start in range(0, len(text_indexes), MAX_BATCH_SIZE):
            batch_indexes = text_indexes[
                batch_start:batch_start + MAX_BATCH_SIZE
            ]
            batch_texts = [
                texts[index][:MAX_TEXT_CHARACTERS]
                for index in batch_indexes
            ]
            encoded = tokenizer(
                batch_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            with torch.inference_mode():
                probabilities = torch.sigmoid(model(**encoded).logits).tolist()

            for index, scores in zip(batch_indexes, probabilities):
                results[index] = _possible_allergens(labels, scores)
    except RuntimeError as error:
        raise AllergenModelUnavailable(
            "ローカルモデルでアレルゲン候補を判定できませんでした。"
        ) from error

    return results

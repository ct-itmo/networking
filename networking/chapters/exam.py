from datetime import datetime, timezone
from decimal import Decimal

from networking.core.chapter.exam import (
    ExamChapter,
    ExamPollForm,
    ExamQuestion,
    RenderedQuestion,
)

RESULTS_VISIBLE = False

EXAM_START = datetime(2026, 6, 16, 9, 0, 0, tzinfo=timezone.utc)
EXAM_END = datetime(2026, 6, 16, 11, 0, 0, tzinfo=timezone.utc)


ATTEND_PROMPT = (
    "<p>Придёте ли вы на устный экзамен, если наберёте 74 балла? Отсутствие ответа "
    "будет обозначать «Нет».</p>"
)


class ExamVariant:
    rendered: dict[str, RenderedQuestion]

    def __init__(self, user_id: int):
        self.rendered = {}

        self._poll("attend", ATTEND_PROMPT, [("yes", "Да"), ("no", "Нет")])

    def _poll(self, slug: str, prompt: str, choices: list[tuple[str, str]]) -> None:
        """A single-choice poll: optional, never graded, no points."""
        self.rendered[slug] = RenderedQuestion(
            prompt=prompt, form_class=ExamPollForm.make_task(slug, choices=choices)
        )


QUESTIONS: list[ExamQuestion] = [
    ExamQuestion("attend", "Устный экзамен", Decimal(0)),
]


exam_chapter = ExamChapter(
    name="Письменный тест",
    start=EXAM_START,
    end=EXAM_END,
    results_visible=RESULTS_VISIBLE,
    questions=QUESTIONS,
    variant_factory=ExamVariant,
)


__all__ = ["exam_chapter", "RESULTS_VISIBLE"]

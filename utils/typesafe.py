import os
from typing import Optional

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from utils import logger


HATE_CATEGORIES = {
    "none": "No harmful content present",
    "incitement_to_crime": "Public call or incitement to commit crimes / repeat an illegal act",
    "approval_of_arbitrary_action": "Approval or glorification of an illegal, discriminatory action against a group",
    "incitement_to_hatred": "Incitement to hatred, hostility or dehumanization against a group",
    "insult": "Defamatory or hateful insult against a person or group",
    "threat": "Threat or incitement to violence against a person or group",
    "glorification_of_nazism": "Approval, glorification or denial of National Socialist crimes",
    "religious_defamation": "Defamation or denigration of a religion or its adherents",
    "other": "Other harmful or illegal content not covered above",
}

SEVERITY_LEVELS = [
    "No harm",
    "Mild: borderline or implicit",
    "Moderate: clear harmful intent",
    "Severe: blatant, dehumanizing or inciting violence",
]


class TypeSafeLLMClient:
    """Comment classifier backed by TypeSafe's Jev (System One) model.

    Jev evaluates typed questions against a state and returns structured
    decisions (Choice, Score, Noul) with calibrated probabilities. There is
    no LLM fallback and no text to parse.
    """

    def __init__(
        self,
        model: str = "jev-latest",
        context: Optional[str] = None,
    ):
        self.model = model
        self.context = context or ""
        self.api_key = os.environ.get("TYPESAFE_API_KEY") or ""
        if not self.api_key:
            logger.fatal("TYPESAFE_API_KEY environment variable is required but not set!")
        self.client = TypeSafeClient(api_key=self.api_key)

    def _state(self, comment: Text) -> Text:
        if self.context:
            return f"Context:\n{self.context}\n\nComment:\n{comment}"
        return f"Comment:\n{comment}"

    def _build_questions(self):
        return {
            "harmful": Noul(
                instructions=(
                    "The comment contains hate speech, incitement to hatred, "
                    "dehumanization, threat, or approval of illegal acts "
                    "against a protected group."
                )
            ),
            "category": Choice(
                instructions="Which category best describes the comment's content?",
                criteria=HATE_CATEGORIES,
            ),
            "severity": Score(
                instructions="How severe is the harmful content in the comment?",
                criteria=SEVERITY_LEVELS,
            ),
        }

    def classify(self, comment: Text) -> dict:
        """Classify a comment with TypeSafe Jev.

        Returns a dict of category scores in the 0-1 probability range so the
        result stays compatible with the threshold-based flagging used in the
        existing pipeline. ``category`` holds the discrete category choice.
        """
        response = self.client.system_one(
            model=self.model,
            state=self._state(comment),
            questions=self._build_questions(),
        )

        answers = response.answers
        category_answer = answers["category"]
        severity_answer = answers["severity"]
        harmful_answer = answers["harmful"]

        probabilities = getattr(category_answer, "probabilities", {}) or {}
        scores = {label: float(p) for label, p in probabilities.items()}
        scores["harmful"] = float(harmful_answer.noul)
        scores["category"] = category_answer.choice
        scores["confidence"] = float(getattr(category_answer, "confidence", 0.0))
        scores["severity"] = float(severity_answer.score)

        print(
            f"TypeSafe Jev: category={category_answer.choice} "
            f"harmful={harmful_answer.noul:.3f} "
            f"severity={severity_answer.score:.2f} "
            f"confidence={scores['confidence']:.3f}"
        )
        return scores

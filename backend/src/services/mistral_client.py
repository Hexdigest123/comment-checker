"""
Mistral client for Moderation 2 API
Adapted from existing utils/llm.py
"""

import os
from typing import Text, Any, Dict

from mistralai.client import Mistral

from ..config import get_settings

# Get settings
settings = get_settings()


class LLMClient:
    """
    Client for Mistral Moderation 2 API with fallback in-context check.
    """

    def __init__(
        self,
        model: Text = "mistral-moderation-2603",
        context: Text = None,
    ):
        self.model = model
        self.context = context or ""
        self.api_key = settings.mistral_api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Mistral API Key not found. Set MISTRAL_API_KEY in environment.")
        self.client = Mistral(api_key=self.api_key)

    def classify(self, comment: Text) -> Dict[str, float]:
        """
        Classify comment using Mistral Moderation 2 API.
        
        Returns raw category scores from Mistral Moderation 2.
        """
        response = self.client.classifiers.moderate(
            model=self.model,
            inputs=[comment]
        )
        
        result = response.results[0]
        category_scores = result.category_scores
        
        # Convert to float values
        scores = {label: float(score) for label, score in category_scores.items()}
        
        return scores

    def check_with_context(self, comment: Text) -> bool:
        """
        Use a general-purpose Mistral model with context to detect hate speech.
        
        This is the second-stage check for comments that Mistral Moderation 2
        did not flag but may contain subtle hate speech.
        
        Args:
            comment: The comment text to analyze
            
        Returns:
            True if the comment contains hate speech, False otherwise
        """
        prompt = f"""
You are a hate speech detection assistant. Judge the comment STRICTLY within the
given context. The context is the situation the comment is reacting to; the
comment's meaning depends on it.

Context: {self.context}

Comment: "{comment}"

A comment is hate speech in this context if, read as a reaction to the situation
above, it does ANY of the following:
- Approves, praises, justifies, glorifies, or calls for imitation of a hateful
  or illegal act against a protected group (e.g. banning or expelling people
  because of their ethnicity or religion). This is hate speech EVEN IF the
  comment's words alone are innocuous - a phrase like "man of honor", "best man",
  "he did nothing wrong", or a single praising emoji can be hate speech when it
  endorses a hateful act in this context.
- Expresses prejudice, hostility, dehumanization, or discrimination against a
  protected group, directly or by coded language / dog whistles.
- Calls for, threatens, or incites violence or further exclusion of a group.

Do not judge the comment in isolation. Do not require the comment to contain
slurs or explicit hateful words on its own. The question is whether, given the
context, a reasonable person would understand this comment as hateful.

Respond with ONLY the word "YES" if the comment is hate speech in this context,
or "NO" if it is not. Do not add any explanation, justification, or additional
text. Just "YES" or "NO".
"""
        
        response = self.client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {
                    "role": "system",
                    "content": "You are a hate speech detection assistant. Judge the comment in the given context, not in isolation. A comment that endorses a hateful act described in the context is hate speech even if its words are innocuous. Respond ONLY with YES or NO."
                },
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.0,
        )
        
        result = response.choices[0].message.content.strip().upper()
        is_hate = result == "YES"
        
        return is_hate

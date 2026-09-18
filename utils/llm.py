import os
from typing import Optional, Text
from mistralai.client import Mistral
from utils import logger


class LLMClient:
    def __init__(
        self,
        model: Text = "mistral-moderation-2603",
        context: Optional[str] = None,
    ):
        self.model = model
        self.context = context
        self.api_key = os.environ.get("MISTRAL_API_KEY") or ""
        if not self.api_key:
            logger.fatal("MISTRAL_API_KEY environment variable is required but not set!")
        self.client = Mistral(api_key=self.api_key)

    def classify(self, comment: Text) -> dict:
        """Classify comment using Mistral Moderation 2 API.
        
        Returns raw category scores from Mistral Moderation 2.
        """
        response = self.client.classifiers.moderate(
            model=self.model,
            inputs=[comment]
        )
        
        result = response.results[0]
        category_scores = result.category_scores
        
        print(f"Mistral Moderation 2 scores: {category_scores}")
        return category_scores

    def check_with_context(self, comment: Text) -> bool:
        """Use a general-purpose Mistral model with context to detect hate speech.
        
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
  comment's words alone are innocuous — a phrase like "man of honor", "best man",
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
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.0,
        )
        
        result = response.choices[0].message.content.strip().upper()
        is_hate = result == "YES"
        
        print(f"Context-aware check: {comment} -> {result}")
        return is_hate

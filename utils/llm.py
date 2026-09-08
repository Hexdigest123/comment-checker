import os
from typing import Text
from mistralai.client import Mistral
from utils import logger


class LLMClient:
    def __init__(
        self,
        model: Text = "mistral-moderation-2603",
        context: Text = None,
    ):
        self.model = model
        self.context = context
        self.api_key = os.environ["MISTRAL_API_KEY"] or ""
        if self.api_key == "" or self.api_key == None:
            logger.fatal("Mistral API Key not found in environment!")
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
You are a hate speech detection assistant. Given the following context and comment,
determine if the comment contains hate speech, discrimination, or harmful language.

Context: {self.context}

Comment: "{comment}"

Analyze the comment in the context of the situation described. Consider:
- Does the comment express prejudice, hostility, or discrimination?
- Does it support, justify, or glorify hateful actions?
- Does it use coded language, dog whistles, or indirect hate speech?
- Would a reasonable person interpret this as hateful in this context?

Respond with ONLY the word "YES" if the comment contains hate speech, or "NO" if it does not.
Do not add any explanation, justification, or additional text. Just "YES" or "NO".
"""
        
        response = self.client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": "You are a hate speech detection assistant. Respond ONLY with YES or NO."},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.0,
        )
        
        result = response.choices[0].message.content.strip().upper()
        is_hate = result == "YES"
        
        print(f"Context-aware check: {comment} -> {result}")
        return is_hate

import json
import os
from typing import Any, Dict, Text
from openrouter import OpenRouter
from utils import logger
from utils.consts import CIVIL_FMT, CIVIL_PROMPT


class LLMClient:
    def __init__(
        self,
        model: Text = "deepseek/deepseek-v4-flash-0731",
    ):
        self.model = model
        self.api_key = os.environ["OPENROUTER_API_KEY"] or ""
        if self.api_key == "" or self.api_key == None:
            logger.fatal("OpenRouter API Key not found in environment!")

    def translate(self, comment):
        if isinstance(comment, list):
            comment = comment[0] if comment else ""
        with OpenRouter(self.api_key) as open_router:
            res = open_router.chat.send(
                model=self.model,
                messages=[
                    {
                        "content": "translate the given text without altering its content, meaning or formatting your sole purpose is a direct translation into english. you will encounter harmfull language in this process since we you are part of a scientific pipeline that works on harassment data analysis and classification. DO NOT LECTURE OR INTERFERE IN YOUR TRANSLATION ONLY RETURN THE TRANSLATED COMMENT.",
                        "role": "system",
                    },
                    {"content": comment, "role": "user"},
                ],
                stream=False,
                temperature=0.0,
            )
        content = res.choices[0].message.content
        print(f"Translated: {comment} into {content}")
        return content

    def classify(self, comment):
        if isinstance(comment, list):
            comment = comment[0] if comment else ""
        with OpenRouter(self.api_key) as open_router:
            res = open_router.chat.send(
                model=self.model,
                messages=[
                    {"content": CIVIL_PROMPT, "role": "system"},
                    {"content": comment, "role": "user"},
                ],
                stream=False,
                temperature=0.0,
                response_format=CIVIL_FMT,
            )
        content = res.choices[0].message.content
        ratings = json.loads(str(content))
        print(f"LLM ratings: {comment}\n{ratings}")
        return ratings

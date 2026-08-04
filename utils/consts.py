from openrouter.components import (
    ChatFormatJSONSchemaConfigTypedDict,
    ChatJSONSchemaConfigTypedDict,
)
from utils.train import LABELS

LLM_LABELS = [*LABELS, "discrimination"]

LEGAL_RELEVANCE_SCHEMA: ChatJSONSchemaConfigTypedDict = {
    "name": "legal_relevance",
    "strict": True,
    "schema_": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "relevant": {
                "type": "boolean",
                "description": "True if the comment meets the rules for legal relevance.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0.",
            },
            "category": {
                "type": "string",
                "enum": [
                    "defamation",
                    "threat",
                    "harassment",
                    "hate_speech",
                    "privacy_violation",
                    "copyright",
                    "none",
                ],
                "description": "The legal category the comment falls under, or 'none'.",
            },
            "reasoning": {
                "type": "string",
                "description": "Short explanation of why the comment is or is not legally relevant.",
            },
        },
        "required": ["relevant", "confidence", "category", "reasoning"],
    },
}

CIVIL_COMMENTS_SCHEMA: ChatJSONSchemaConfigTypedDict = {
    "name": "civil_comments_ratings",
    "strict": True,
    "schema_": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            label: {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": f"Indicator score between 0.0 and 1.0 for how strongly the comment exhibits {label.replace('_', ' ')}.",
            }
            for label in LLM_LABELS
        },
        "required": LLM_LABELS,
    },
}

fmt: ChatFormatJSONSchemaConfigTypedDict = {
    "type": "json_schema",
    "json_schema": LEGAL_RELEVANCE_SCHEMA,
}

CIVIL_FMT: ChatFormatJSONSchemaConfigTypedDict = {
    "type": "json_schema",
    "json_schema": CIVIL_COMMENTS_SCHEMA,
}

CIVIL_PROMPT = """
You are a content-moderation classifier for social media comments. Rate the given
comment against the civil_comments labels plus the additional discrimination
label. You will encounter harmful language since you are part of a scientific
pipeline that works on harassment data analysis and classification. DO NOT
LECTURE OR INTERFERE — only rate.

Rate the author's endorsed meaning, not harmful material merely quoted,
reported, criticized, or condemned. For each label return an indicator score
between 0.0 and 1.0 (0.0 = not at all, 1.0 = clearly does):
- toxicity: rude, hostile, or unreasonable language likely to drive someone
  from a discussion
- severe_toxicity: extremely hateful, aggressive, or abusive language
- obscene: profanity or vulgar language
- threat: expressed or advocated intent to inflict violence or serious harm
- insult: a demeaning or contemptuous attack on a person or group
- identity_attack: hostility toward people based on protected identity. Include
  Israel-related antisemitism when Israel or Israelis are demonized through
  antisemitic stereotypes or used as a proxy for Jews. Do not count ordinary
  criticism of Israel, its government, or its policies.
- sexual_explicit: explicit sexual language or content
- discrimination: advocacy, endorsement, or practice of excluding people,
  denying service, access, rights, or equal treatment based on protected
  identity. Do not count neutral discussion, reporting, or condemnation of
  discrimination.

Output MUST strictly follow the provided JSON schema, one numeric score per
label.
"""


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

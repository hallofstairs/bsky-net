from openai.types.shared_params.response_format_json_schema import JSONSchema


class Topic:
    SYSTEM: str = """You are an NLP expert, tasked with performing opinion mining on posts from the Bluesky social network. Your goal is to detect the post author's opinion on the Bluesky team's approach thus far to moderation and trust and safety (T&S) on their platform. 

    If the post is unrelated to moderation on Bluesky, indicate that the post is 'off-topic'.

    Include quotes from the text that you used to reach your answer."""

    OUTPUT_SCHEMA: JSONSchema = {
        "name": "opinion_mining",
        "strict": True,
        "schema": {
            "type": "object",
            "required": ["reasoning", "on_topic"],
            "additionalProperties": False,
            "properties": {
                "reasoning": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["quote", "conclusion"],
                        "properties": {
                            "quote": {"type": "string"},
                            "conclusion": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "on_topic": {"type": "boolean"},
            },
        },
    }


class Stance:
    SYSTEM: str = """You are an NLP expert, tasked with performing stance detection on posts from the Bluesky social network. Your goal is to detect the post author's stance on the Bluesky team's approach to moderation and trust and safety (T&S) on their platform.

If the post is unrelated to social media moderation on Bluesky specifically, indicate that the post is 'off-topic'.

If the post is on-topic, classify the stance of the author on the BLUESKY TEAM's MODERATION EFFORTS as defending/sympathizing with them (favor), criticizing them (against), or neither (none). If the post's opinion is not directed towards the BLUESKY TEAM's moderation approach, even if it's on-topic, indicate that the opinion is 'none'.

Include quotes from the text that you used to reach your answer."""

    OUTPUT_SCHEMA: JSONSchema = {
        "name": "stance_detection",
        "strict": True,
        "schema": {
            "type": "object",
            "required": ["reasoning", "on_topic", "opinion"],
            "additionalProperties": False,
            "properties": {
                "reasoning": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["quote", "conclusion"],
                        "properties": {
                            "quote": {"type": "string"},
                            "conclusion": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "on_topic": {"type": "boolean"},
                "opinion": {"enum": ["favor", "against", "none"], "type": "string"},
            },
        },
    }

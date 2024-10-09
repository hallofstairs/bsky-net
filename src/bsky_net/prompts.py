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

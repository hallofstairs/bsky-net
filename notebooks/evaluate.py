# %% Imports

import json
import os
import re
import time
import typing as t

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# %% Load eval

EVAL_PATH = "../evals/stance-eval-01-subset.csv"
df = pd.read_csv(EVAL_PATH)

# DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
# client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=DEEPSEEK_KEY)
# TOGETHER_KEY = os.getenv("TOGETHER_API_KEY")
# client = OpenAI(base_url="https://api.together.xyz/v1", api_key=TOGETHER_KEY)
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

SYSTEM_PROMPT = """
You are a stance detection classifier that analyzes explicit and implicit opinions toward a topic. For each Bluesky post, determine:
1. Stance: "favor", "against", or "none" toward the topic, or "off-topic" if the post is not related to the topic.
2. Intensity: Strength of the author's sentiment (e.g., mild vs. vehement).
3. Seriousness: Whether the stance is earnest (serious) or undercut by humor/sarcasm.
4. Confidence: Your certainty in the classification.

Use the post's language, tone, context, and cultural/subtextual cues (e.g., irony, exaggeration) to infer these dimensions.

Response format:
{
    "reasoning": "Explain stance, intensity, and seriousness with text examples (e.g., 'high intensity due to strong language: <quote>'). Address sarcasm/jokes if detected.",
    "answer": "favor" | "against" | "none" | "off-topic",
    "intensity": "high" | "medium" | "low",
    "seriousness": "high" | "medium" | "low",
    "confidence": "high" | "medium" | "low"
}
"""

USER_PROMPT = """
<context>
{context}
</context>

<topic>
{topic}
</topic>

<post>
{text}
</post>
"""


class ResponseFormat(t.TypedDict):
    reasoning: str
    answer: t.Literal["favor", "against", "none", "off-topic"]
    intensity: t.Literal["high", "medium", "low"]
    seriousness: t.Literal["high", "medium", "low"]
    confidence: t.Literal["high", "medium", "low"]


class BskySD:
    TOPIC = "Bluesky's moderation approach"
    CONTEXT = """Bluesky's approach to content and community management prioritizes user autonomy through decentralized choice: minimal safety baselines (e.g., illegal content removal) with tools for users/communities to self-define rules via opt-in filters, labels, or third-party tools—rejecting top-down control in favor of a customizable, pluralistic ecosystem. 

(Focus: User/community agency over rigid enforcement, opt-in flexibility.)"""


model = "gpt-4o-mini"
model_suffix = model.split("/")[-1] + "-promptV6"

predictions = []
for idx, row in df.iterrows():
    if not pd.isna(row.get(f"{model_suffix}_answer")):
        print(f"Skipping row {idx} - already processed")
        continue

    text = row["text"]
    prompt = USER_PROMPT.format(context=BskySD.CONTEXT, topic=BskySD.TOPIC, text=text)

    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        latency_ms = (time.time() - start_time) * 1000
        print(f"Request latency: {latency_ms:.0f}ms")

        print(f"Processing row {idx}")
        print("POST: ", text)
        response = response.choices[0].message

        is_deepseek = "deepseek-reasoner" == model

        if is_deepseek:
            if response.content is None or response.reasoning_content is None:  # type: ignore
                raise ValueError("No response from DeepSeek")
            answer: ResponseFormat = json.loads(response.content)
            thinking: str = response.reasoning_content  # type: ignore

        else:
            content = response.content
            if content is None:
                raise ValueError("No response content")

            # Extract thinking from <think> tags if present
            thinking_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
            thinking = thinking_match.group(1).strip() if thinking_match else ""

            # Find JSON block in the response
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
            if not json_match:
                # Fallback to finding any JSON-like content
                json_match = re.search(r"\{.*?\}", content, re.DOTALL)

            if not json_match:
                raise ValueError("Could not parse response JSON")

            answer = json.loads(
                json_match.group(1) if "```json" in content else json_match.group(0)
            )
        print("REASONING: ", thinking)
        print("PRED: ", json.dumps(answer, indent=2))

        # Update prediction immediately
        df.at[idx, f"{model_suffix}_answer"] = answer["answer"]
        df.at[idx, f"{model_suffix}_intensity"] = answer["intensity"]
        df.at[idx, f"{model_suffix}_seriousness"] = answer["seriousness"]
        df.at[idx, f"{model_suffix}_confidence"] = answer["confidence"]
        df.at[idx, f"{model_suffix}_thinking"] = thinking

        # Save progress after each prediction
        df.to_csv(EVAL_PATH, index=False)

    except Exception as e:
        print(f"Error processing row {idx}: {str(e)}")
        continue

# %%

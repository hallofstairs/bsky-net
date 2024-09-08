# %% Imports

import json
import random
import re

from bsky_net import Post, records

# %% Constants

STREAM_DIR = "../data/raw/stream-2023-07-01"
EXPERIMENTS_DIR = "../data/experiments"

START_DATE = "2023-05-25"
END_DATE = "2023-05-26"

KEYWORDS = [
    " moderation",
    "moderator",
    "moderators",
    "moderating",
    "moderated",
    " mods ",
    "t&s",
    " ts ",
    "trust and safety",
    # "dev",
    "bluesky team",
    "bsky team",
    "bluesky devs",
    "bsky devs",
    # "nazi",
    # "harass",
    "trigger",
    # "hellthread",
    "alice",
    "censor",
    "porn",
    " ban ",
    "permaban",
    # "crisis",
    # "bigot",
    # " mute ",
    # " block ",
    "keep out",
    "trolls",
    # "abuse",
    # "protocol",
    "tolerance",
    # "discourse",
    "leadership",
    "criti",
    "malicious",
    "removal",
    "aggressive",
    # "beta",
    "address",
    "experiment",
    # "asshole",
    "removal",
    # "rules",
    "suspended",
    "bad actor",
    "@pfrazee.com",
    "@jay.bsky.team",
]

HARDCODED_URIS = [
    "at://did:plc:xum72mip7ti5niwqbgpvaqn4/app.bsky.feed.post/3jwjdb7thtk2f",
    "at://did:plc:skdtaqm6rsfyzxkhm52annce/app.bsky.feed.post/3jwkjcs3bq323",
    "at://did:plc:ankl45qhcj3diso7xccejhvw/app.bsky.feed.post/3jwla77tjfk26",
    "at://did:plc:4t2ziwnnescprzorvmrfduey/app.bsky.feed.post/3jwjhkteeq22f",
    "at://did:plc:rj4i3rfzwlj5zlqhx6435taq/app.bsky.feed.post/3jwjio3c4q22z",
    "at://did:plc:67fotfrfx52bicz2enuqnxhx/app.bsky.feed.post/3jwjis3levc2z",
    "at://did:plc:jum3jqmjyb5lendchskg2viv/app.bsky.feed.post/3jwjiscmtqf2x",
    "at://did:plc:jum3jqmjyb5lendchskg2viv/app.bsky.feed.post/3jwjj73skr22z",
    "at://did:plc:izqtoh6lvty2sk7riyhuefgk/app.bsky.feed.post/3jwjjcazrzs2f",
    "at://did:plc:ywbm3iywnhzep3ckt6efhoh7/app.bsky.feed.post/3jwjtwm2r342f",
    "at://did:plc:tbo4hkau3p2itkar2vsnb3gp/app.bsky.feed.post/3jwjhqbjnhc2z",
    "at://did:plc:kzgjymzlya5hezpidllt5tfm/app.bsky.feed.post/3jwl2a6mppl23",
    "at://did:plc:b4par5yri3f2docr7qjvafr3/app.bsky.feed.post/3jwljxp6fml2o",
    "at://did:plc:yteysv5adlllg4e3xek3e3uk/app.bsky.feed.post/3jwjcpuvhy22r",
    "at://did:plc:vnjkyosaxdimztkjsap2qkrs/app.bsky.feed.post/3jwjiirq2wt2e",
    "at://did:plc:5ksfzq5xa5u5wbis3qtxofmh/app.bsky.feed.post/3jwjjbobovs2z",
    "at://did:plc:uxn6n6mhzgtl63mxzugioaut/app.bsky.feed.post/3jwjjd76bcs2v",
    "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jwjg5deo5s2f",
    "at://did:plc:ragtjsm2j2vknwkz3zp4oxrd/app.bsky.feed.post/3jwjcd66ods2j",
    "at://did:plc:gxj3piolqxy4a6g53gjwj4wt/app.bsky.feed.post/3jwjgzcsxns2z",
    "at://did:plc:ndnkcgglid6ylmhdqvi22n4z/app.bsky.feed.post/3jwjferjk5k2p",
    "at://did:plc:6xaygnxrj6pya3lgs7ksgii6/app.bsky.feed.post/3jwjgx24zxs2f",
    "at://did:plc:xgjcudwc5yk4z2uex5v6e7bl/app.bsky.feed.post/3jwkwi5uvtk25",
    "at://did:plc:vwzwgnygau7ed7b7wt5ux7y2/app.bsky.feed.post/3jwjalqlq5d2s",
    "at://did:plc:tbtvvcvghlofiyz7r2vmlpwm/app.bsky.feed.post/3jwjqsavrgt2q",
    "at://did:plc:4f7jjc6lesf7wdd4wxaftqv5/app.bsky.feed.post/3jwkq6z7w3t2p",
    "at://did:plc:oky5czdrnfjpqslsw2a5iclo/app.bsky.feed.post/3jwqmujzrzq2u",
]

# %% Generate test set

kw_regex = re.compile(
    r"\b(?:" + "|".join(map(re.escape, KEYWORDS)) + r")\b", re.IGNORECASE
)

SAMPLE_PCT = 0.10

total_posts = 0
last_date = ""


for record in records(
    stream_dir=STREAM_DIR, start_date="2023-05-24", end_date="2023-05-30"
):
    if record["$type"] == "app.bsky.feed.post":
        post = Post(**record)  # TODO: Fix $type in __init__.py

        # Ignore replies (for now)
        if "reply" in post and post["reply"]:
            continue

        if "embed" in post and post["embed"]:
            continue

        # Bot accounts
        if post["did"] in [
            "did:plc:jvhf36loasspmffobuyfpopz",
            "did:plc:74432b52s3ceyfnwdgxjsog5",
        ]:
            continue

        # TODO: Hardcode certain URIs to include
        if kw_regex.search(post["text"].lower()):
            if post["uri"] in HARDCODED_URIS or random.random() <= SAMPLE_PCT:
                with open(f"{EXPERIMENTS_DIR}/test-set.jsonl", "a") as log_file:
                    json.dump(post, log_file)
                    log_file.write("\n")

                total_posts += 1
                last_date = post["createdAt"]

print(total_posts)

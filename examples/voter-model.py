import json
import random

from bsky_net.types import UserTimestep
from bsky_net.utils import did_from_uri

# Load dataset
with open("../data/processed/impressions-2023-01-01.json") as file:
    impressions: dict[str, dict[str, UserTimestep]] = json.load(file)

# Initialize opinions (randomly)
opinions = {
    user_did: random.choice([-1, 0, 1])
    for user_updates in impressions.values()
    for user_did in user_updates.keys()
}

# Run voter model
for timestep, user_updates in impressions.items():
    new_opinions = {}

    for consumer_did, consumer_impressions in user_updates.items():
        # Skip users who have no impressions for that timestep
        if not consumer_impressions["consumed"]:
            continue

        # Select a random producer to adapt opinion from
        producers = list(
            {did_from_uri(uri) for uri in consumer_impressions["consumed"].keys()}
        )
        random_producer = random.choice(producers)
        new_opinion = opinions[random_producer]

        # Assign new opinion
        new_opinions[consumer_did] = new_opinion

    # Update opinions reference
    opinions = {**opinions, **new_opinions}


# Print some basic statistics
print(f"Number of users: {len(opinions)}")

# TODO: Graph opinions over time
# TODO: Make this into a notebook so that you can see the results
# TODO: Show the error over time

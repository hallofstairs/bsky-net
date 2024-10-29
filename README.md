# ${\normalsize B}{\small SKY-}{\normalsize N}{\small ET}$

🚧 _Under development_ 🚧

The goal of `bsky-net` is to benchmark belief dynamics models, assessing their accuracy in predicting actual beliefs and enabling comparisons between different models.

Concretely, `bsky-net` is a temporal graph dataset of user connections, communications, and beliefs over time, using real data from the Bluesky social network. These three components enable more accurate depictions of network structure, timing of belief updates, and measurement of model accuracy, respectively.

`bsky-net` uses a newly-available, nearly-complete record of over 1 billion interactions on the Bluesky social network. As of 8/27/24, the data includes:

- 6.2M users
- \>300M posts (including quotes, replies)
- \>1B likes
- \>100M follows
- Among other events, like reposts, blocks, etc.

<!-- ## Setup

This project uses UV to manage the Python environment. It's new (and unstable), but it's the best way to manage Python environments that I've found. You can install it [here](https://docs.astral.sh/uv/getting-started/installation/)

1. Ensure you have uv installed. You can check that uv is available by running the `uv` command:

   ```bash
   $ uv
   An extremely fast Python package manager.
   Usage: uv [OPTIONS] <COMMAND>
   ...
   ```

2. Clone the repository:

   ```
   git clone https://github.com/hallofstairs/bsky-net.git
   cd bsky-net
   ```

3. Create a virtual environment:

   ```
   uv venv
   ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

Now your environment is set up and ready for development or running the examples. -->

<!-- ## Data

The raw data used in this project is too large to be stored within the GitHub repo–it can be found on Hugging Face [here](https://huggingface.co/datasets/hallofstairs/bluesky) and can be downloaded to your local machine using `scripts/download-data.py`.

Once you have downloaded the raw data, you can generate `bsky-net` using `scripts/process-data.py`.

You can also just download `bsky-net` from Hugging Face. (TODO)

<!-- The data used in this project is available in the `data/raw/` directory. The data is not included in this repository due to size constraints, but it can be downloaded from Hugging Face using the following command:

TODO



TODO -->

<!-- If you're interested in crawling the network from scratch yourself, shoot me an email [jetthollister@pm.me](mailto:jetthollister@pm.me) and I'll help you get started.

## Examples

The `examples/` directory contains several sample notebooks demonstrating the usage of bsky-net:

> **Note:** Make sure you have the necessary data files in the `data/processed/` directory before running the notebooks on your own machine.

- `voter-model.ipynb`: Simple voter model simulation -->

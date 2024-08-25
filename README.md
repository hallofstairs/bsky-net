# bsky-net

🚧 _Under development_ 🚧

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

The data structures and algorithms used in this project are _not_ currently optimized for large-scale analysis, but rather for understanding how the benchmark can be used (and improved!) for validating opinion dynamics models.

## Data

The data used in this project is available in the `data/raw/` directory. The data is not included in this repository due to size constraints, but it can be downloaded from Hugging Face using the following command:

TODO

Once you have downloaded the data, you can generate the processed version of the dataset with the following command:

TODO

If you're interested in crawling the network from scratch yourself, shoot me an email [jetthollister@pm.me](mailto:jetthollister@pm.me) and I'll help you get started.

## Examples

The `examples/` directory contains several sample notebooks demonstrating the usage of bsky-net:

- `voter-model.ipynb`: Simple voter model simulation

> **Note:** Make sure you have the necessary data files in the `data/processed/` directory before running the notebooks on your own machine. The data files are not included in this repository due to size constraints.

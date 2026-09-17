FROM python:3.12-slim

# uv/uvx for the rewardkit verifier (runs in this container after the agent)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Analysis libraries, preinstalled so the agent need not hit the network.
RUN pip install --no-cache-dir pandas numpy scipy statsmodels pyyaml

# The dataset under analysis.
COPY data.csv /app/data.csv

# The decision specification and the universes to sweep. These are the agent's
# instructions in machine-readable form; the prose in instruction.md matches.
COPY astra.yaml /app/astra.yaml
COPY universes/ /app/universes/

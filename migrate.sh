#!/bin/bash

# Check for uv
if ! command -v uv &> /dev/null
then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

echo "Starting MySQL to PostgreSQL Migration..."
uv run main.py

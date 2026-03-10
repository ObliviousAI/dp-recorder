# Use a lightweight Python 3.11 base image
FROM python:3.11-slim

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Set the working directory inside the container
WORKDIR /workspaces/dp-recorder

# Copy ONLY the dependency files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to NOT use virtual environments (since Docker itself is an isolated environment)
# and install the dependencies (excluding your own package code for now).
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Now copy the rest of your application code into the container
COPY . .

# Install the project itself (so your library can be imported anywhere in the tests)
RUN poetry install --no-interaction --no-ansi

# Set the default command to open an interactive bash shell
CMD ["bash"]
# Use a Python image with uv pre-installed
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies
# Copy only the files needed to install dependencies first (for caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Place the virtual environment in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port (Render sets PORT, but we default to 8050)
EXPOSE 8050

# Run the application using Gunicorn
# Render will automatically inject the PORT environment variable.
# We use the shell form to allow variable expansion.
CMD gunicorn dsp_filter_design.app:server --bind 0.0.0.0:$PORT

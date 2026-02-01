# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# gcc and others might be needed for some python packages like multidict or yarl if wheels aren't available
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Cloud Run injects PORT environment variable, which keep_alive.py should use.
# Discord bots are persistent processes, but Cloud Run is request-based.
# We need to expose a port (web server) to keep the instance alive/satisfy Cloud Run's health check.
ENV PORT=8080

# Command to run the bot
CMD ["python", "bot.py"]

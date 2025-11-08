# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# Explicitly add the working directory to the Python path
# This ensures modules like 'utils' can be found
ENV PYTHONPATH=/app

# Copy the requirements file first for caching
# This assumes you run 'docker build .' from WITHIN the 'telegram_bot' directory
COPY ../requirements.txt .
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- THIS IS THE FIX ---
# Copy the contents of the current directory (the build context)
# into the container's /app directory
COPY . .
# --- END FIX ---

# Define the command to run your bot
CMD ["python", "bot.py"]
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first for caching
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire telegram_bot directory into the container
COPY . .

# Define the command to run your bot
# This is the command Koyeb will run to start your worker
CMD ["python", "bot.py"]
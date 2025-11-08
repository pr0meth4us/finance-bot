# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# --- THIS IS THE FIX ---
# Explicitly add the working directory to the PYTHONPATH
# This ensures that modules like 'utils' and 'handlers' are findable.
ENV PYTHONPATH=/app

# Copy the requirements file first for caching
COPY ../requirements.txt .
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the contents of the telegram_bot directory into the container's /app directory
# NOTE: The trailing slash is important. It copies the *contents* of telegram_bot.
COPY ./telegram_bot/ .
# Define the command to run your bot
CMD ["python", "bot.py"]
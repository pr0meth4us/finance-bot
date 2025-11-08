# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# --- FIX 1: Add Python Path ---
# Add the working directory to the Python path to find modules like 'utils'
ENV PYTHONPATH=/app

# --- FIX 2: Correct requirements.txt path ---
# Copy the requirements file from the build context (project root)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX 3: Correct code copy path ---
# Copy only the contents of the 'telegram_bot' directory
# (from the build context) into the container's /app directory
COPY ./telegram_bot .

# Define the command to run your bot
CMD ["python", "bot.py"]
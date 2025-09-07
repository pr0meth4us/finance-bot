# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
# Replace "Asia/Phnom_Penh" with your desired timezone (e.g., "America/New_York", "Etc/UTC").
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first for caching
# Assuming this Dockerfile is inside the telegram_bot directory
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code from the telegram_bot directory
COPY . .

# Define the command to run your bot
CMD ["python", "bot.py"]

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first for caching
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- THIS IS THE FIX ---
# Copy only the contents of the telegram_bot directory into the container's /app directory
COPY ./telegram_bot .

# Define the command to run your bot
CMD ["python", "bot.py"]


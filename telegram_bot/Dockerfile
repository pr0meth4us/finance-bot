# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory in the container
WORKDIR /app

# --- FIX 1 ---
# Add the working directory to the Python path to find modules like 'utils'
ENV PYTHONPATH=/app

# --- FIX 2 ---
# Copy the requirements file from the build context (project root)
COPY requirements.txt .
# --- END FIXES ---

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the contents of the telegram_bot directory into the container's /app directory
# This line was correct in the original file
COPY ./telegram_bot .
# Define the command to run your bot
CMD ["python", "bot.py"]
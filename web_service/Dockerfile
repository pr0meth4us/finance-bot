# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the timezone for the container.
# Replace "Asia/Phnom_Penh" with your desired timezone (e.g., "America/New_York", "Etc/UTC").
ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file from the repository root
# Assuming this Dockerfile is inside the web_service directory
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the web_service directory contents to /app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=run.py

# Run the application using the run.py file directly
CMD ["python", "run.py"]

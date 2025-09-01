# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file from the repository root
COPY requirements.txt .

# Install dependencies (make sure gunicorn is in requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the web_service directory contents to /app
COPY web_service/ .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define the command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "run:app"]
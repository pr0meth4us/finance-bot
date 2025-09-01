# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file from the repository root
COPY requirements.txt .

# Install dependencies and gunicorn explicitly
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy the web_service directory contents to /app
COPY web_service/ .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Use Python to run the app as fallback if gunicorn fails
CMD ["python", "run.py"]
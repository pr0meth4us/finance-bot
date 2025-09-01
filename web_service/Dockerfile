# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file from the repository root
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the contents of the web_service folder from the repository root
# into the container's /app directory
COPY web_service/ .

# Make port 8000 available
EXPOSE 8000

# Define the command to run your app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's layer caching
COPY ../requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- THIS IS THE FIX ---
# Copy only the contents of the web_service directory into the container's /app directory
COPY ./web_service .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define the command to run your app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's layer caching
COPY ../requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire web_service directory into the container
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define the command to run your app using Gunicorn
# This is the command Koyeb will run to start your web service
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
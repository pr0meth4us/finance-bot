# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file from the repository root
COPY requirements.txt .

# Install dependencies (including gunicorn)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the web_service directory contents to /app
COPY web_service/ .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Use Python to run the Flask app directly
CMD ["python", "-c", "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=8000, debug=False)"]
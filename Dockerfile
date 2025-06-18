# Use an official Python runtime as a parent image
FROM python:3.10-slim 

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by Chrome and webdriver-manager
# This might vary slightly based on the base image and exact needs
RUN apt-get update && apt-get install -y \
    procps \
    wget \
    unzip \
    gnupg \
    # For Chrome/Chromedriver:
    xvfb \
    libnss3 \
    libgconf-2-4 \
    # Add any other dependencies your scrapers or app might need
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code and data files into the container
COPY . . 
# This copies main.py, scrapers/, course_content.json, discourse_posts_json, content_embeddings.json (if including in image)

# Make port 8000 available to the world outside this container (Cloud Run will map it)
EXPOSE 8000

# Define environment variable for the port (Cloud Run sets this)
ENV PORT 8000 
# ENV AIPIPE_TOKEN your_token_here # Better to set this in Cloud Run service config

# Command to run your application using uvicorn
# Cloud Run expects the app to listen on 0.0.0.0 and the port specified by $PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
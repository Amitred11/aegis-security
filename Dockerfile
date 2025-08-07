# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Prevent python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure python output is sent straight to the terminal
ENV PYTHONUNBUFFERED 1

# Install system dependencies if any
# RUN apt-get update && apt-get install -y ...

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the Spacy model
RUN python -m spacy download en_core_web_lg

# Copy the application code into the container
COPY ./aegis_toolkit /app/aegis_toolkit
COPY ./AegisApp /app/AegisApp

# The port the app will run on
EXPOSE 8000

# Command to run the application
# We run from inside the AegisApp directory
CMD ["uvicorn", "AegisApp.main:app", "--host", "0.0.0.0", "--port", "8000"]
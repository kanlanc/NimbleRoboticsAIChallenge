# Base image
FROM python:3.7-buster

# Install libsrtp development library
RUN apt-get update && apt-get install -y \
    libsrtp2-dev \
    libgl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Install dependencies
RUN pip install  -r requirements.txt

# Expose ports for communication
EXPOSE 9001 9002

# Command to run the client script
CMD ["python", "./client.py"]
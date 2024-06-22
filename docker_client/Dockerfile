# Base image
FROM python:3.7-buster

# Create server directory
WORKDIR /client

# Copy client script and requirements file
COPY ./client.py ./client.py
COPY ./requirements.txt /client

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose ports for communication
EXPOSE 9001 9002

# Command to run the client script
CMD ["python", "./client.py"]
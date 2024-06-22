# Base image
FROM python:3.7-buster

# Create server directory
WORKDIR /server

# Copy server script and requirements file
COPY ./server.py ./server.py
COPY ./requirements.txt /server

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose ports for communication
EXPOSE 9001 9002

# Command to run the server script
CMD ["python", "./server.py"]
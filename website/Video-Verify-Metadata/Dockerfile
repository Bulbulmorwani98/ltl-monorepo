# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY app /app

# Copy the certs folder into the container at /app/certs
COPY certs /app/certs

#The tests folder probably should not be built unless for a local build and test.
COPY tests /app/tests

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install procps to get ps command
RUN apt-get update && apt-get install -y procps net-tools

# Make port 80 available to the world outside this container
EXPOSE 80

# Run the Flask app
CMD ["python", "app.py"]
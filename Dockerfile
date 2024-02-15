# Use an official Python runtime as the parent image
FROM python:3.9-slim

ENV TZ=Asia/Hong_Kong

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Run your script when the container launches
CMD ["python", "main.py"]

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy only the requirements.txt first to leverage Docker cache
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Run the script when the container launches
CMD ["python", "./chatgpt_curator.py"]

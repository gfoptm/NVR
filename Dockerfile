FROM python:3.7-slim-buster

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install git, build dependencies, and required libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-python-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gcc \
    python3-dev

RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Install wheel
RUN pip install wheel

# Clone face_recognition_models repository
# RUN git clone --depth 1 https://github.com/ageitgey/face_recognition_models.git
RUN pip install --upgrade setuptools

# Install face_recognition_models
RUN cd face_recognition_models && python setup.py install

# Install dlib from PyPI
RUN pip install dlib

# Change working directory back to /app
WORKDIR /app

# Make port 80 available to the world outside this container
EXPOSE 80

# Run main.py when the container launches
CMD ["python", "main.py"]

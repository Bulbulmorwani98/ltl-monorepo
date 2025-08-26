# Use an official Python runtime as a parent image
FROM python:3.10

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

RUN apt-get update 
# Copy the requirements file into the container
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Set correct permissions for static files
RUN mkdir -p /app/static /app/media
RUN chmod -R 755 /app/static /app/media
 
# Run the Django development server
CMD ["gunicorn", "--config", "gunicorn.conf.py", "longtail.wsgi:application"] 
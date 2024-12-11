# Use Alpine Linux as the base image for a lightweight container
FROM python:3.11-alpine

# Install necessary dependencies for WeasyPrint
RUN apk update && apk add --no-cache \
    build-base \
    libffi-dev \
    postgresql-dev \
    mysql-client \
    sqlite-dev \
    bash \
    cairo-dev \
    pango-dev \
    gdk-pixbuf-dev \
    libjpeg-turbo-dev \
    libxml2-dev \
    libxslt-dev

# Install Python dependencies
RUN pip install --no-cache-dir -U pip setuptools

# Install web framework and libraries
RUN pip install flask flask-sqlalchemy flask-wtf weasyprint

# Set working directory
WORKDIR /app

# Copy the application code into the container
COPY . /app

# Expose the port the app will run on
EXPOSE 5000

# Set the entrypoint for the app
CMD ["python", "app.py"]
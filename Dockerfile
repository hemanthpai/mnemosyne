FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Install dependencies
COPY ./backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code
COPY ./backend /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "memory_service.wsgi:application"]
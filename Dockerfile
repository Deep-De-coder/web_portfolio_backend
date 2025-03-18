# Use official Python image
FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Flask will run on
EXPOSE 5000

# Start Gunicorn with the correct port
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "server:app"]
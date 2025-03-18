# Use official Python image
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install dependencies first (cached if unchanged)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Set environment variables
ENV PORT=10000

# Expose the correct port
EXPOSE 10000

# Start Gunicorn with the correct port
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:10000", "server:app"]

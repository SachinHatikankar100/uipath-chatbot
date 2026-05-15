# Multi-stage build for UiPath Chatbot
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy project files needed for pip install
COPY requirements.txt .
COPY pyproject.toml .
COPY README.md .
# Create package directory structure for editable install
#RUN mkdir -p uipath_chatbot - not needed for uipath chatbot app hence commented
#COPY uipath_chatbot/__init__.py uipath_chatbot/ - not needed for uipath chatbot app hence commented

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (curl is required for HEALTHCHECK)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Create directories for generated reports and logs
RUN mkdir -p /app/generated_report /app/logs

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Health check updated it for UiPath chatbot app
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/_stcore/health || exit 1

# Run the application updated it for UiPath chatbot app
CMD ["streamlit", "run", "chatbot.py", "--server.port=8000", "--server.address=0.0.0.0"]

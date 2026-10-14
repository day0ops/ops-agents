FROM python:3.12-slim
WORKDIR /app
COPY mcp-servers/core-banking/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp-servers/core-banking/core_banking ./core_banking
EXPOSE 8000
CMD ["python", "-m", "core_banking.server"]

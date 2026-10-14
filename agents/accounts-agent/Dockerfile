FROM python:3.12-slim
WORKDIR /app
COPY agents/_shared /app/_shared
RUN pip install --no-cache-dir -e /app/_shared -r /app/_shared/requirements.txt
COPY agents/accounts-agent/accounts_agent ./accounts_agent
EXPOSE 8080
CMD ["uvicorn", "accounts_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]

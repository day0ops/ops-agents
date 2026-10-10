FROM python:3.12-slim
WORKDIR /app
COPY ../_shared /app/_shared
COPY requirements.txt .
RUN pip install --no-cache-dir -e /app/_shared && pip install --no-cache-dir -r requirements.txt
COPY repo_agent ./repo_agent
EXPOSE 8080
CMD ["uvicorn", "repo_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]

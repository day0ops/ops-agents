FROM python:3.12-slim
WORKDIR /app
COPY mcp-servers/repo-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp-servers/repo-server/repo_server ./repo_server
EXPOSE 8000
CMD ["python", "-m", "repo_server.server"]

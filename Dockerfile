FROM docker.1panel.live/library/python:3.12-slim
WORKDIR /shebao
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
CMD ["python", "api.py"]
EXPOSE 8020
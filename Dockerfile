FROM python:3.8
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Download the Punkt tokenizer models
RUN python -m nltk.downloader punkt
COPY . .
ENTRYPOINT ["python", "./chatgpt_curator.py"]

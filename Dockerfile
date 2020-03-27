FROM python:3

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE  8080
CMD ["mitmdump", "-k", "-s", "doubletap.py"]
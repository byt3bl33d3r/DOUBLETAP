FROM python:3.8-slim

ARG USER=appuser

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PIP_DISABLE_PIP_VERSION_CHECK on
ENV PIP_NO_CACHE_DIR off
ENV PATH /home/$USER/.local/bin:$PATH

RUN useradd --create-home $USER

WORKDIR /home/$USER/src/doubletap

USER $USER

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE  8080

CMD ["mitmdump", "-v", "--no-http2", "-k", "-s", "doubletap.py"]
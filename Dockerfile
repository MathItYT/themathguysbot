FROM python:3.12-bullseye
WORKDIR /usr/local/app

RUN apt-get update
RUN apt-get install -y texlive-full
RUN apt-get install -y build-essential python3-dev libcairo2-dev libpango1.0-dev

COPY pyproject.toml ./
COPY tmg_bot ./tmg_bot
COPY README.md ./
RUN pip install .

CMD ["tmg-bot"]
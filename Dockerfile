FROM python:3.7-buster as base
FROM base as build

# create virtualenv
RUN python3 -m venv /venv

# activate virtualenv
ENV PATH="/venv/bin:$PATH"

# upgrade pip
RUN pip install --upgrade pip

# add requirements so we can cache them
COPY requirements-dev.txt /install/requirements.txt

RUN pip install -r /install/requirements.txt

# Copy rest of files

COPY . /install/

RUN pip install /install

# Minimize image

FROM python:3.7-slim-buster

# venv
COPY --from=build /venv /venv

# activate virtualenv
ENV PATH="/venv/bin:$PATH"


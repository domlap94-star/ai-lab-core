ARG R02_BASE_IMAGE
FROM ${R02_BASE_IMAGE}

LABEL next-stabil.owner="R02" \
      next-stabil.purpose="isolated-test-environment"

COPY test/r02/requirements.lock /opt/next-stabil-r02/requirements.lock
RUN pip install --no-cache-dir --no-deps \
      -r /opt/next-stabil-r02/requirements.lock \
    && python -m pytest --version

WORKDIR /workspace/backend
ENTRYPOINT ["python"]

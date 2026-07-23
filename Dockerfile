# Builds the api conainer, using a pre existing image we got from docker hub. 
# We are using staging building pattern here to ensure the final image is reduced size.
# This happes because stage 1 we get all the dependencies to do that a lot of usless artifacts are also installed,
# so we need a stage 2 which is for when the image is actually built we only copy the artifacts needed to run the code.

# Stage 1 — builder
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2 — runtime
FROM python:3.11-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create a non-root user and switch to it for security 
RUN adduser --disabled-password --no-create-home bullpen
USER bullpen

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
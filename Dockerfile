ARG TF_VERSION=1.5.7
ARG PYTHON_VERSION=3.11

FROM hashicorp/terraform:$TF_VERSION AS terraform

FROM python:$PYTHON_VERSION-alpine
RUN apk add --update --no-cache graphviz ttf-freefont build-base \
 && pip install -U pip

COPY --from=terraform /bin/terraform /bin/terraform
COPY ./docker-entrypoint.sh /bin/docker-entrypoint.sh
RUN chmod +x /bin/docker-entrypoint.sh

# Create non-root user
RUN addgroup -g 1000 blastradius \
 && adduser -u 1000 -G blastradius -s /bin/sh -D blastradius

WORKDIR /src
COPY . .
RUN pip install -e .

# Create data directory and change ownership
RUN mkdir -p /data && chown -R blastradius:blastradius /data /src

# For S3 mode, we don't need the overlay filesystem so we can run as non-root
# But we need to handle the conditional logic in entrypoint
USER blastradius
WORKDIR /data

EXPOSE 5000

ENTRYPOINT ["/bin/docker-entrypoint.sh"]
CMD ["blast-radius", "--serve"]

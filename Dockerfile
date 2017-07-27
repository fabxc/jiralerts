FROM python:3.6.2-alpine

RUN mkdir -p /opt/jiraalerts

# A valid Jira user
ENV "JIRA_USERNAME" ""

# That users password
ENV "JIRA_PASSWORD" ""

# The full address to the jira server (including the https:// bit)
ENV "JIRA_SERVER" ""

ADD main.py requirements.txt /opt/jiraalerts/

RUN export BUILD_PKGS="build-base musl-dev linux-headers" && \ 
    export RUN_PKGS="tini" && \
        apk add --no-cache ${BUILD_PKGS} ${RUN_PKGS} && \
    pip install --requirement /opt/jiraalerts/requirements.txt && \
    apk del ${BUILD_PKGS}

ENTRYPOINT ["/sbin/tini", "--"]

# Allow the use of environment variables in the CMD. 
# See https://github.com/moby/moby/issues/5509
CMD ["sh", "-c", "python /opt/jiraalerts/main.py $JIRA_SERVER"]


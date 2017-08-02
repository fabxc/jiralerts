FROM python:3.6.2-alpine

RUN mkdir -p /opt/jiralerts

# A valid Jira user
ENV "JIRA_USERNAME" ""

# That users password
ENV "JIRA_PASSWORD" ""

# The full address to the jira server (including the https:// bit)
ENV "JIRA_SERVER" ""

ADD requirements.txt /opt/jiralerts/

RUN export BUILD_PKGS="build-base musl-dev linux-headers" && \ 
    export RUN_PKGS="tini" && \
        apk add --no-cache ${BUILD_PKGS} ${RUN_PKGS} && \
    pip install --requirement /opt/jiralerts/requirements.txt && \
    apk del ${BUILD_PKGS}

ADD main.py /opt/jiralerts/

ENTRYPOINT ["/sbin/tini", "--"]

# Allow the use of environment variables in the CMD. 
# See https://github.com/moby/moby/issues/5509
CMD ["sh", "-c", "python /opt/jiralerts/main.py --host='0.0.0.0' $JIRA_SERVER"]


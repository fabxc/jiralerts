#!/usr/bin/env python3

import os
import sys

import click
from flask import Flask, request, make_response
from jira import JIRA
from jinja2 import Template
import prometheus_client as prometheus
import base64

app = Flask(__name__)

jira = None

summary_tmpl = Template(r'{% if commonAnnotations.summary %}{{ commonAnnotations.summary }}{% else %}{% for k, v in groupLabels.items() %}{{ k }}="{{v}}" {% endfor %}{% endif %}')

description_tmpl = Template(r'''
h2. Common information

{% for k, v in commonAnnotations.items() -%}
* *{{ k }}*: {{ v }}
{% endfor %}

h2. Active alerts

{% for a in alerts if a.status == 'firing' -%}
_Annotations_:
  {% for k, v in a.annotations.items() -%}
* {{ k }} = {{ v }}
  {% endfor %}
_Labels_:
  {% for k, v in a.labels.items() -%}
* {{ k }} = {{ v }}
  {% endfor %}
[Source|{{ a.generatorURL }}]
----
{% endfor %}


alert_group_key={{ groupKey }}
jiraReference={{ jira_reference }}
''')

description_boundary = '_-- Alertmanager -- [only edit above]_'

# Order for the search query is important for the query performance. It relies
# on the 'alert_group_key' field in the description that must not be modified.
search_query = 'project = %s and labels = "alert" and description ~ "alert_group_key=%s"'

jira_request_time = prometheus.Histogram('jira_request_latency_seconds', 'Latency when querying the JIRA API', ['action'])
request_time = prometheus.Histogram('request_latency_seconds', 'Latency of incoming requests')

jira_request_time_transitions = jira_request_time.labels({'action': 'transitions'})
jira_request_time_close = jira_request_time.labels({'action': 'close'})
jira_request_time_reopen = jira_request_time.labels({'action': 'reopen'})
jira_request_time_update = jira_request_time.labels({'action': 'update'})
jira_request_time_create = jira_request_time.labels({'action': 'create'})

@jira_request_time_transitions.time()
def transitions(issue):
    return jira.transitions(issue)

@jira_request_time_close.time()
def close(issue, tid):
    return jira.transition_issue(issue, tid)

@jira_request_time_reopen.time()
def reopen(issue, tid):
    return jira.transition_issue(issue, trans['reopen'])

@jira_request_time_update.time()
def update_issue(issue, summary, description):
    custom_desc = issue.fields.description.rsplit(description_boundary, 1)[0]
    return issue.update(
        summary=summary,
        description="%s\n\n%s\n%s" % (custom_desc.strip(), description_boundary, description))

@jira_request_time_create.time()
def create_issue(project, team, summary, description):
    return jira.create_issue({
        'project': {'key': project},
        'summary': summary,
        'description': "%s\n\n%s" % (description_boundary, description),
        'issuetype': {'name': 'Task'},
        'labels': ['alert', team],
    })

@app.route('/-/health')
def health():
    return "OK", 200

@request_time.time()
@app.route('/issues/<project>/<team>', methods=['POST'])
def file_issue(project, team):
    """
    This endpoint accepts a JSON encoded notification according to the version 3 or 4
    of the generic webhook of the Prometheus Alertmanager.
    """
    data = request.get_json()
    if data['version'] not in ["3", "4"]:
        return "unknown message version %s" % data['version'], 400

    resolved = data['status'] == "resolved"

    # In python 3, base64 must be passed a byte array. However, the supplied argument is
    # a string, unencoded. Thus, it must be converted to an encoded string, base64 encoded, and decoded again
    # for use by jinja
    data['jiraReference'] = base64.b64encode(data['groupKey'].encode('utf-8')).decode('utf-8')

    description = description_tmpl.render(data)
    summary = summary_tmpl.render(data)

    # If there's already a ticket for the incident, update it and reopen/close if necessary.
    result = jira.search_issues(search_query % (project, data['jiraReference']))
    if result:
        issue = result[0]

        # We have to check the available transitions for the issue. These differ
        # between boards depending on setup.
        trans = {}
        for t in transitions(issue):
            trans[t['name'].lower()] = t['id']

        # Try different possible transitions for resolved incidents
        # in order of preference. Different ones may work for different boards.
        if resolved:
            for t in ["resolved", "closed", "done", "complete"]:
                if t in trans:
                    close(issue, trans[t])
                    break
        # For issues that are closed by one of the status definitions below, reopen them.
        elif issue.fields.status.name.lower() in ["resolved", "closed", "done", "complete"]:
            for t in trans:
                if t in ['reopen', 'open']:
                    reopen(issue, trans[t])
                    break

        # Update the base information regardless of the transition.
        update_issue(issue, summary, description)

    # Do not create an issue for resolved incidents that were never filed.
    elif not resolved:
        create_issue(project, team, summary, description)

    return "", 200


@app.route('/metrics')
def metrics():
    resp = make_response(prometheus.generate_latest(prometheus.core.REGISTRY))
    resp.headers['Content-Type'] = prometheus.CONTENT_TYPE_LATEST
    return resp, 200


@click.command()
@click.option('--host', help='Host listen address')
@click.option('--port', '-p', default=9050, help='Listen port for the webhook')
@click.option('--debug', '-d', default=False, is_flag=True, help='Enable debug mode')
@click.argument('server')
def main(host, port, server, debug):
    global jira

    username = os.environ.get('JIRA_USERNAME')
    password = os.environ.get('JIRA_PASSWORD')

    if not username or not password:
        print("JIRA_USERNAME or JIRA_PASSWORD not set")
        sys.exit(2)

    jira = JIRA(basic_auth=(username, password), server=server, logging=debug)
    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    main()


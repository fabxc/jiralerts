# jiralerts

This is a basic JIRA integration for Alertmanager. It receives Alertmanager webhook messages
and files labeled issues for it. If an alert stops firing or starts firing again, tickets
are closed or reopened.

Given how generic JIRA is, the integration attempts several different transitions
that may be available for an issue.

__Consider this an opinionated example snippet. It may not fit your use case without modification.__

## Running it

```
JIRA_USERNAME=<your_username> JIRA_PASSWORD=<your_password> ./main.py 'https://<your_jira>'
```

In your Alertmanager receiver configurations:

```yaml
receivers:
- name: 'jira_issues'
  webhook_configs:
  - url: 'http://<jira_address>/<jira_project>/<single_label>'
```

A typical usage could be a single 'ALERTS' projects where the label in the URL
refers to the affected system or the team that should handle the issue.

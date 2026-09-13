# Incident Response Policy

**Document owner:** Security Operations · **Last reviewed:** April 2026

## Severity definitions

Incidents are classified on a four-level scale. A Sev-1 incident is one with
confirmed unauthorized access to customer data or a total loss of service for
all customers. A Sev-2 incident is a significant degradation of service or a
credible but unconfirmed indication of compromise. Sev-3 and Sev-4 cover
localized faults and minor issues with no customer impact.

## Response targets

The on-call security engineer acknowledges a Sev-1 incident within 15 minutes,
at any hour. A Sev-2 incident is acknowledged within one hour during business
hours. Once acknowledged, an incident commander is appointed for every Sev-1 and
Sev-2 incident, and that person is explicitly not the person performing the
remediation work.

## Communication

For any incident confirmed to involve unauthorized access to customer data,
affected customers are notified within 72 hours of confirmation. Notification is
sent by the incident commander and reviewed by the General Counsel before it is
sent. A status page update is published within 30 minutes for any incident that
degrades service for more than one customer.

## Investigation

Every Sev-1 and Sev-2 incident is followed by a written post-incident review
completed within five business days. The review is blameless, identifies
contributing causes, and produces tracked remediation items with named owners
and due dates. Post-incident reviews are retained indefinitely.

## Testing

The incident response process is exercised twice a year through a tabletop
simulation involving Security Operations, Engineering, and Legal. Findings from
each exercise are tracked to closure in the same system used for post-incident
review items.

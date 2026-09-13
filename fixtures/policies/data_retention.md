# Data Retention Policy

**Document owner:** Privacy and Data Governance · **Last reviewed:** February 2026

## Purpose

This policy defines how long the company retains categories of data and how
that data is disposed of at the end of its retention period.

## Retention periods

Application logs are retained for 90 days in hot storage and are then deleted
automatically. Security audit logs, including authentication events and
administrative actions, are retained for 13 months to support investigations.
Customer account records are retained for the life of the contract and for a
further 90 days after termination, after which they are purged.

Backups of production databases are retained for 35 days on a rolling basis.
Backup media is encrypted and stored in a separate region from the primary
production environment.

Support tickets and their attachments are retained for two years from the date
the ticket is closed. Recruitment records for unsuccessful candidates are
retained for six months.

## Customer deletion requests

Customers may request deletion of their data at any time. Deletion requests are
completed within 30 days of a verified request. Deletion propagates to backups
at the end of the 35-day backup cycle rather than immediately, and the customer
is informed of this timeline when the request is acknowledged.

## Disposal

Data that has reached the end of its retention period is deleted by automated
jobs that run nightly. Physical media that has held customer data is destroyed
by a certified disposal vendor, and certificates of destruction are retained for
three years.

## Exceptions

Where data is subject to a legal hold, the retention period is suspended for
the duration of the hold. Legal holds are issued only by the General Counsel and
are recorded in the legal hold register.

# Access Control Policy

**Document owner:** Security Engineering · **Last reviewed:** March 2026

## Scope

This policy governs access to all production systems, internal administrative
tools, and customer data stores operated by the company. It applies to all
employees, contractors, and temporary staff.

## Authentication

All access to production systems requires multi-factor authentication. Hardware
security keys are issued to every engineer with production access, and SMS is
not accepted as a second factor under any circumstance. Single sign-on is
mandatory for all internal applications; direct local accounts on production
hosts are prohibited except for a single documented break-glass account whose
credentials are held in a sealed vault.

## Authorization

Access is granted on a least-privilege basis. Engineers receive read-only access
to production by default, and elevated write access must be requested through a
ticket, approved by the engineer's manager, and approved a second time by a
member of the Security Engineering team. Standing administrative access is not
granted to any individual; elevated sessions are time-boxed to four hours and
expire automatically.

## Reviews and revocation

User access rights are formally reviewed every quarter. The review is performed
by Security Engineering together with each department head, and any account that
has not been used in 60 days is disabled. All access for departing employees is
revoked within 24 hours of their final day, and the revocation is verified by a
second reviewer.

## Shared credentials

Shared accounts are not permitted. Where a system genuinely cannot support
individual accounts, an exception must be approved in writing by the Head of
Security, recorded in the exception register, and reviewed at each quarterly
access review.

## Enforcement

Violations of this policy are treated as a security incident and are escalated
to the Head of Security. Repeated violations may result in termination of
access or employment.

# Doola Partner API — reference

Condensed from `https://docs.doola.com/api/introduction` and the linked pages.
Discovery index: `https://docs.doola.com/llms.txt`.

## What it is

Create customers, submit company formations (LLC or C-Corp), retrieve formation
documents, and look up reference data. Formation is asynchronous and delivered over
webhooks.

## Environments

| Environment | Base URL | Key prefix |
|---|---|---|
| Sandbox | `https://api.test.doola.com` | `dk_test_` |
| Production | `https://api.doola.com` | `dk_live_` |

Always build and test against sandbox first. Sandbox keys never trigger real state
filings or charges.

## Authentication

Every request carries the key in the `Authorization` header. The `Authorization` value
is the raw key (`dk_test_...`), not a bearer token.

```
curl https://api.test.doola.com/v1/partner/customers \
  -X POST \
  -H "Authorization: <api key>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key-001" \
  -d '{"email":"jane@example.com","firstName":"Jane","lastName":"Doe",
       "phoneNumber":"+121****0100","countryOfResidence":"USA"}'
```

A successful response returns a `doolaCustomerId`. Save it — a company formation needs it.

## How formation works

Two steps, then asynchronous progress over webhooks.

1. **Create a customer** — returns `doolaCustomerId`. One customer can own many companies.
2. **Submit a company formation** — call Create company with the `doolaCustomerId` and
   company details. `entityType` is `LLC` (default) or `CCorp`. This starts the formation.
3. **Track progress with webhooks** — formation is asynchronous. **Do not poll.**

## Key concepts

- **Idempotency.** Create endpoints require an `Idempotency-Key` header. Use a unique key
  per logical operation. Retrying with the same key and body is safe and never
  duplicates. If a create fails, the key is released — fix the request and retry with the
  same key. Once a create succeeds, reusing its key with a different body returns
  `409 E_IDEMPOTENCY_KEY_REUSED`.
- **Submission status is not formation.** `formationSubmissionStatus` describes what
  Doola is doing with the request. Actual formation state lives on the Formation service.
- **Webhooks.** Verify `X-Doola-Signature` (HMAC-SHA256 over the raw body). Delivery is
  at-least-once with retries at 1m / 15m / 1h / 12h / 24h; then the endpoint is
  auto-disabled. Generate the signing secret yourself in the Partner Portal.

## Entity requirements

- **LLC** — takes `members`.
- **CCorp** — takes `executiveMembers` (President, Secretary, Treasurer, Director; the
  first three appear once each) plus `ccorpValuation`.

## Addresses

Exactly two are expected: one `mailing` and one `business`. A `registeredAgent` entry
omits the address object entirely.

## Non-US founders and EIN

When nobody supplies a valid US tax ID, the IRS needs a signed **SS-4** before the EIN,
and **Form 8821** for an expedited EIN. An ITIN does not waive signing. Read
`signatureRequirements` on the company record.

Expedited EIN:

```json
{"requestedServices": [{"service": "EinCreation", "variant": "Expedite"}]}
```

## Getting access

Credentials come from the Doola team: https://www.doola.com/partner-with-us/

## Custody rule

The API key and webhook secret are secrets. They live in local custody
(`DOOLA_API_KEY` env or a local secrets file), never in source, a chat transcript, a URL,
a QR payload, or a published page. SSN/ITIN values are collected locally, sent straight
to the API, and redacted from every emitted line.

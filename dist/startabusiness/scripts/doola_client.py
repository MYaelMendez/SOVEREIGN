#!/usr/bin/env python3
"""
doola_client.py -- Doola Partner API client for ae://#startabusiness->

Wires real US company formation (LLC / C-Corp) into the sovereign business
runtime. Formation is the legal link of the chain: it turns an agentic page
into a registered entity that can hold a bank account and take payment.

Docs: https://docs.doola.com/api/introduction

ae:// chain rules encoded here
------------------------------
custody   The API key and the webhook signing secret live in the environment
          or in C:\\ae\\secrets\\doola.json. They are never hardcoded, never
          printed, never written to a surface, never put in a URL or a QR.
gate      Sandbox is the default. Production requires DOOLA_ENV=production
          AND a dk_live_ key. A dk_test_ key aimed at production (or the
          reverse) is refused. Default-deny.
contract  Every create carries an Idempotency-Key. A retry with the same key
          and the same body returns the original result and never duplicates.
verify    `selftest` proves request construction, payload validation,
          idempotency, error branching and webhook HMAC offline -- no
          credentials and no network required.

Never move a secret
-------------------
SSN / ITIN values are collected locally, sent directly to Doola, and redacted
from every line this client emits. They never enter a chat transcript, a URL,
a QR payload, or a public surface.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SANDBOX_BASE = "https://api.test.doola.com"
PRODUCTION_BASE = "https://api.doola.com"
API_PREFIX = "/v1/partner"

VAULT_PATH = pathlib.Path(r"C:\ae\secrets\doola.json")

ENTITY_TYPES = ("LLC", "CCorp")
ADDRESS_PROVIDERS = ("partner", "registeredAgent", "doola")
ADDRESS_KINDS = ("mailing", "business")

# Events this client knows how to react to.
WEBHOOK_EVENTS = (
    "company_formation_submitted",
    "company_formation_failed",
    "company_formation_completed",
    "company_ein_issued",
    "document_aoo_uploaded",
    "document_einletter_uploaded",
    "partner_webhook_disabled",
)

# The two signals the docs warn against confusing.
SUBMISSION_STATUSES = ("PENDING", "SUBMITTED", "FAILED")
SERVICE_STATUSES = ("InProgress", "Completed")

# Matches a US SSN in either dashed or bare form.
_SSN_RE = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
_SECRET_KEY_RE = re.compile(r"(ssn|itin|taxid|tax_id|password|secret|apikey|api_key)", re.I)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class DoolaError(Exception):
    """A machine-readable error returned by, or raised before, the API."""

    def __init__(self, code: str, message: str, status: int | None = None,
                 request_id: str | None = None, details: Any = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status
        self.request_id = request_id
        self.details = details

    def is_idempotency_conflict(self) -> bool:
        return self.code in ("E_IDEMPOTENCY_KEY_REUSED", "E_IDEMPOTENCY_IN_PROGRESS")

    def is_retryable(self) -> bool:
        """Per the docs: a pre-commit 4xx or a transient 5xx releases the key,
        so the same key may be retried after fixing the request."""
        if self.status is None:
            return False
        return self.status >= 500 or self.code == "E_IDEMPOTENCY_IN_PROGRESS"


class SecretRefused(Exception):
    """Raised when a value that must never leave the machine is about to."""


# --------------------------------------------------------------------------
# Redaction -- the 'never move a secret' rule, in code
# --------------------------------------------------------------------------


def redact(value: Any) -> Any:
    """Deep-copy a payload with SSN/ITIN-shaped values masked.

    Applied before anything is printed or written. Returns a new object; the
    input is not modified.
    """
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and _SECRET_KEY_RE.search(k):
                out[k] = "***redacted***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _SSN_RE.sub("***-**-****", value)
    return value


def assert_no_secret_leak(text: str) -> str:
    """Refuse to emit text carrying an SSN-shaped value."""
    if _SSN_RE.search(text):
        raise SecretRefused(
            "refused: the text carries an SSN-shaped value. Collect it locally "
            "and send it straight to the API; never log, print or publish it."
        )
    return text


# --------------------------------------------------------------------------
# Credentials -- custody
# --------------------------------------------------------------------------


def _read_vault() -> dict:
    if not VAULT_PATH.exists():
        return {}
    try:
        return json.loads(VAULT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def resolve_api_key(env: dict | None = None) -> str:
    """env var first, then the local vault file. Never a literal in source."""
    env = env if env is not None else os.environ
    key = (env.get("DOOLA_API_KEY") or "").strip()
    if key:
        return key
    key = (_read_vault().get("apiKey") or "").strip()
    if key:
        return key
    raise DoolaError(
        "E_NO_API_KEY",
        "No Doola API key. Set DOOLA_API_KEY or add C:\\ae\\secrets\\doola.json "
        "with {\"apiKey\": \"dk_test_...\"}. Request access at "
        "https://www.doola.com/partner-with-us/",
    )


def resolve_webhook_secret(env: dict | None = None) -> str:
    env = env if env is not None else os.environ
    sec = (env.get("DOOLA_WEBHOOK_SECRET") or "").strip()
    if sec:
        return sec
    sec = (_read_vault().get("webhookSecret") or "").strip()
    if sec:
        return sec
    raise DoolaError(
        "E_NO_WEBHOOK_SECRET",
        "No webhook signing secret. Set DOOLA_WEBHOOK_SECRET or add "
        "{\"webhookSecret\": \"...\"} to C:\\ae\\secrets\\doola.json.",
    )


def resolve_base(env: dict | None = None) -> str:
    """Sandbox unless DOOLA_ENV says production, explicitly."""
    env = env if env is not None else os.environ
    return PRODUCTION_BASE if (env.get("DOOLA_ENV") or "").strip().lower() == "production" else SANDBOX_BASE


def guard_key_environment(api_key: str, base_url: str) -> None:
    """Refuse to send a test key to production or a live key to sandbox."""
    is_live = api_key.startswith("dk_live_")
    is_test = api_key.startswith("dk_test_")
    if base_url == PRODUCTION_BASE and is_test:
        raise SecretRefused("refused: a dk_test_ key may never be sent to production.")
    if base_url == SANDBOX_BASE and is_live:
        raise SecretRefused("refused: a dk_live_ key may never be sent to sandbox.")


def new_idempotency_key() -> str:
    """One key per logical operation. UUID4 per the docs' own example."""
    return str(uuid.uuid4())


# --------------------------------------------------------------------------
# Payload validation -- the documented business rules, as a gate
# --------------------------------------------------------------------------


def validate_company_payload(payload: dict) -> dict:
    """Validate the invariants the docs state, before anything is sent.

    Returns the payload with entityType defaulted. Raises DoolaError with a
    code naming the exact rule that failed.
    """
    if not isinstance(payload, dict):
        raise DoolaError("E_VALIDATION", "company payload must be an object")

    entity = payload.get("entityType", "LLC")
    if entity not in ENTITY_TYPES:
        raise DoolaError("E_VALIDATION", f"entityType must be one of {ENTITY_TYPES}, got {entity!r}")
    payload = {**payload, "entityType": entity}

    # exactly two addresses: one mailing, one business
    addrs = payload.get("addresses")
    if not isinstance(addrs, list) or len(addrs) != 2:
        raise DoolaError("E_VALIDATION", "addresses must hold exactly two entries: one mailing, one business")
    kinds = [a.get("kind") for a in addrs if isinstance(a, dict)]
    if sorted(k for k in kinds if k) != sorted(ADDRESS_KINDS):
        raise DoolaError("E_VALIDATION", "addresses must contain exactly one 'mailing' and one 'business'")
    for a in addrs:
        if not isinstance(a, dict):
            raise DoolaError("E_VALIDATION", "each address entry must be an object")
        if not a.get("provider"):
            raise DoolaError("E_VALIDATION", "each address entry needs a provider")
        if a["provider"] == "registeredAgent":
            if "address" in a:
                raise DoolaError("E_VALIDATION", "a registeredAgent address omits the address object entirely")
            continue
        addr = a.get("address")
        if not isinstance(addr, dict):
            raise DoolaError("E_VALIDATION", "a partner-supplied address needs an address object")
        for field in ("line1", "city", "state", "postalCode", "country"):
            if not addr.get(field):
                raise DoolaError("E_VALIDATION", f"address.{field} is required")

    # entity-specific parties
    if entity == "LLC":
        if not payload.get("members"):
            raise DoolaError("E_VALIDATION", "an LLC takes members")
    else:
        execs = payload.get("executiveMembers")
        if not isinstance(execs, list) or not execs:
            raise DoolaError("E_VALIDATION", "a CCorp takes executiveMembers")
        roles = [e.get("role") for e in execs if isinstance(e, dict)]
        for required in ("President", "Secretary", "Treasurer", "Director"):
            if required not in roles:
                raise DoolaError("E_VALIDATION", f"a CCorp executive team must include a {required}")
        for once_only in ("President", "Secretary", "Treasurer"):
            if roles.count(once_only) > 1:
                raise DoolaError("E_VALIDATION", f"{once_only} may appear only once")
        if payload.get("ccorpValuation") is None:
            raise DoolaError("E_VALIDATION", "a CCorp takes ccorpValuation")

    # person addresses require a phone
    people = list(payload.get("members") or []) + list(payload.get("executiveMembers") or [])
    if payload.get("responsibleParty"):
        people.append(payload["responsibleParty"])
    for p in people:
        if isinstance(p, dict) and isinstance(p.get("address"), dict):
            if not p["address"].get("phone"):
                raise DoolaError("E_VALIDATION", "a person address requires phone")

    services = payload.get("requestedServices")
    if services is not None:
        if not isinstance(services, list):
            raise DoolaError("E_VALIDATION", "requestedServices must be a list")
        for s in services:
            if not isinstance(s, dict) or not s.get("service"):
                raise DoolaError("E_VALIDATION", "each requestedServices entry needs a service")

    return payload


def expedited_ein_service() -> dict:
    """The documented shape for prioritized EIN processing (non-US founders)."""
    return {"service": "EinCreation", "variant": "Expedite"}


# --------------------------------------------------------------------------
# Webhooks -- signature verification
# --------------------------------------------------------------------------


def verify_webhook(raw_body: bytes, signature: str, secret: str) -> bool:
    """HMAC SHA256 hex of the raw body, keyed with the webhook secret.

    Compared in constant time. Header name X-Doola-Signature (frameworks often
    lowercase it).
    """
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def parse_webhook(raw_body: bytes) -> dict:
    """Parse the delivery envelope. Only eventPayload changes shape."""
    doc = json.loads(raw_body.decode("utf-8"))
    return {
        "event": doc.get("event"),
        "eventPayload": doc.get("eventPayload"),
        "known": doc.get("event") in WEBHOOK_EVENTS,
    }


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


class DoolaClient:
    """Sandbox-first Doola Partner API client.

    Refuses to touch production without DOOLA_ENV=production.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 timeout: int = 30, allow_production: bool = False):
        self.base = base_url or resolve_base()
        self.api_key = api_key or resolve_api_key()
        guard_key_environment(self.api_key, self.base)
        if self.base == PRODUCTION_BASE and not allow_production:
            raise SecretRefused(
                "refused: production formation moves real money and real filings. "
                "Pass --live to confirm."
            )
        self.timeout = timeout

    # -- transport ---------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None,
                 idempotency_key: str | None = None) -> tuple[int, Any]:
        url = self.base + API_PREFIX + path
        headers = {
            "Authorization": self.api_key,   # raw key, not a Bearer token
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status, raw = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            raise DoolaError("E_TRANSPORT", f"could not reach {self.base}: {exc.reason}") from exc

        doc = json.loads(raw) if raw.strip() else {}
        err = doc.get("error") if isinstance(doc, dict) else None
        if err:
            raise DoolaError(err.get("code", "E_UNKNOWN"), err.get("message", ""),
                             status, err.get("requestId"), err.get("details"))
        if status >= 400:
            raise DoolaError("E_HTTP", f"HTTP {status}", status)
        return status, (doc.get("payload", doc) if isinstance(doc, dict) else doc)

    # -- customers ---------------------------------------------------------

    def create_customer(self, *, email: str, first_name: str, last_name: str,
                        phone_number: str | None = None,
                        country_of_residence: str = "USA",
                        idempotency_key: str | None = None) -> tuple[int, Any]:
        body = {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "countryOfResidence": country_of_residence,
        }
        if phone_number:
            body["phoneNumber"] = phone_number
        return self._request("POST", "/customers", body, idempotency_key or new_idempotency_key())

    def get_customer(self, customer_id: str) -> tuple[int, Any]:
        return self._request("GET", f"/customers/{customer_id}")

    def list_customers(self, search: str | None = None, page: int = 1) -> tuple[int, Any]:
        q = f"?page={page}" + (f"&search={urllib.parse.quote(search)}" if search else "")
        return self._request("GET", f"/customers{q}")

    # -- companies ---------------------------------------------------------

    def create_company(self, payload: dict,
                       idempotency_key: str | None = None) -> tuple[int, Any]:
        """Submit a formation. Validated locally against the documented rules."""
        validated = validate_company_payload(payload)
        return self._request("POST", "/companies", validated,
                             idempotency_key or new_idempotency_key())

    def get_company(self, company_id: str) -> tuple[int, Any]:
        return self._request("GET", f"/companies/{company_id}")

    def list_companies(self, customer_id: str | None = None, page: int = 1) -> tuple[int, Any]:
        q = f"?page={page}" + (f"&customerId={customer_id}" if customer_id else "")
        return self._request("GET", f"/companies{q}")

    # -- reference data ----------------------------------------------------

    def reference(self, kind: str) -> tuple[int, Any]:
        allowed = {"states", "countries", "naics", "fees"}
        if kind not in allowed:
            raise DoolaError("E_VALIDATION", f"reference kind must be one of {sorted(allowed)}")
        path = {"states": "/reference/states", "countries": "/reference/countries",
                "naics": "/reference/naics", "fees": "/reference/state-filing-fees"}[kind]
        return self._request("GET", path)

    # -- sandbox playground ------------------------------------------------

    def playground_complete_formation(self, company_id: str) -> tuple[int, Any]:
        """Sandbox only: simulate the state confirming formation."""
        if self.base != SANDBOX_BASE:
            raise SecretRefused("refused: the playground is sandbox-only.")
        return self._request("POST", f"/playground/companies/{company_id}/complete-formation")

    def playground_complete_ein(self, company_id: str) -> tuple[int, Any]:
        """Sandbox only: simulate the IRS issuing the EIN."""
        if self.base != SANDBOX_BASE:
            raise SecretRefused("refused: the playground is sandbox-only.")
        return self._request("POST", f"/playground/companies/{company_id}/complete-ein")


# --------------------------------------------------------------------------
# Progress -- the two signals, kept distinct
# --------------------------------------------------------------------------


def formation_progress(company: dict) -> dict:
    """Read a company without confusing submission status with formation.

    `formationSubmissionStatus` says what doola is doing with the request.
    The Formation *service* status says whether the state has confirmed.
    """
    services = company.get("services") or []
    formation = next((s for s in services if s.get("service") == "Formation"), None)
    ein_svc = next((s for s in services if s.get("service") == "EinCreation"), None)
    return {
        "submission": company.get("formationSubmissionStatus"),
        "formation": (formation or {}).get("status"),
        "einService": (ein_svc or {}).get("status"),
        "formed": (formation or {}).get("status") == "Completed",
        "ein": company.get("ein"),
        "filingDate": company.get("formationFilingDate"),
        "filingNumber": company.get("formationFilingNumber"),
        "signatureRequirements": company.get("signatureRequirements") or [],
        "adminNotes": company.get("adminNotes") or [],
    }


# --------------------------------------------------------------------------
# Selftest -- offline proof, no credentials, no network
# --------------------------------------------------------------------------


def _ok_llc() -> dict:
    return {
        "customerId": "cust_123",
        "companyName": "Sovereign Labs LLC",
        "entityType": "LLC",
        "state": "WY",
        "members": [{
            "firstName": "Jane", "lastName": "Doe",
            "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                        "postalCode": "82001", "country": "USA", "phone": "+13075550100"},
        }],
        "addresses": [
            {"kind": "mailing", "provider": "partner",
             "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                         "postalCode": "82001", "country": "USA"}},
            {"kind": "business", "provider": "registeredAgent"},
        ],
    }


def _ok_ccorp() -> dict:
    base = _ok_llc()
    base.pop("members")
    base["entityType"] = "CCorp"
    base["ccorpValuation"] = 1_000_000
    base["executiveMembers"] = [
        {"role": "President", "firstName": "Jane", "lastName": "Doe",
         "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                     "postalCode": "82001", "country": "USA", "phone": "+13075550100"}},
        {"role": "Secretary", "firstName": "Jane", "lastName": "Doe",
         "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                     "postalCode": "82001", "country": "USA", "phone": "+13075550100"}},
        {"role": "Treasurer", "firstName": "Jane", "lastName": "Doe",
         "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                     "postalCode": "82001", "country": "USA", "phone": "+13075550100"}},
        {"role": "Director", "firstName": "Jane", "lastName": "Doe",
         "address": {"line1": "1 Void St", "city": "Cheyenne", "state": "WY",
                     "postalCode": "82001", "country": "USA", "phone": "+13075550100"}},
    ]
    return base


def selftest() -> int:
    """Run every offline check. Returns 0 when all pass."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception as exc:  # noqa: BLE001 - the point is to catch everything
            results.append((name, False, f"{type(exc).__name__}: {exc}"))

    # 1. sandbox is the default; production needs the literal word
    def t_base():
        assert resolve_base({}) == SANDBOX_BASE, "default must be sandbox"
        assert resolve_base({"DOOLA_ENV": "sandbox"}) == SANDBOX_BASE
        assert resolve_base({"DOOLA_ENV": "production"}) == PRODUCTION_BASE
        assert resolve_base({"DOOLA_ENV": "prod"}) == SANDBOX_BASE, "only the literal 'production' opts in"
    check("base_url: sandbox default, explicit production", t_base)

    # 2. key/environment guard
    def t_guard():
        guard_key_environment("dk_test_x", SANDBOX_BASE)
        guard_key_environment("dk_live_x", PRODUCTION_BASE)
        for key, base in (("dk_test_x", PRODUCTION_BASE), ("dk_live_x", SANDBOX_BASE)):
            try:
                guard_key_environment(key, base)
                raise AssertionError(f"should have refused {key[:8]} at {base}")
            except SecretRefused:
                pass
    check("guard: test key never reaches production (and vice versa)", t_guard)

    # 3. idempotency keys are unique per operation
    def t_idem():
        keys = {new_idempotency_key() for _ in range(500)}
        assert len(keys) == 500, "idempotency keys must not collide"
    check("idempotency: 500 keys, 500 distinct", t_idem)

    # 4. payload validation accepts the documented good shapes
    def t_valid_ok():
        validate_company_payload(_ok_llc())
        validate_company_payload(_ok_ccorp())
        # entityType omitted still means LLC -- but an LLC always needs its members
        bare = _ok_llc(); bare.pop("entityType")
        assert validate_company_payload(bare)["entityType"] == "LLC"
    check("validate: LLC and CCorp payloads accepted", t_valid_ok)

    # 5. and rejects the documented bad ones
    def t_valid_bad():
        cases = []
        p = _ok_llc(); p["addresses"] = p["addresses"][:1]; cases.append(p)
        p = _ok_llc(); p["addresses"] = [p["addresses"][0], dict(p["addresses"][0])]; cases.append(p)
        p = _ok_llc(); p.pop("members"); cases.append(p)
        p = _ok_ccorp(); p["executiveMembers"] = p["executiveMembers"][:3]; cases.append(p)
        p = _ok_ccorp(); p["executiveMembers"] = p["executiveMembers"] + [p["executiveMembers"][0]]; cases.append(p)
        p = _ok_llc(); p["entityType"] = "S-Corp"; cases.append(p)
        p = _ok_llc(); p["addresses"][1] = {"kind": "business", "provider": "registeredAgent",
                                            "address": {"line1": "x"}}; cases.append(p)
        for i, bad in enumerate(cases):
            try:
                validate_company_payload(bad)
                raise AssertionError(f"case {i} should have been rejected")
            except DoolaError:
                pass
    check("validate: 7 malformed payloads rejected", t_valid_bad)

    # 6. webhook HMAC
    def t_webhook():
        secret, body = "whsec_test", b'{"event":"company_formation_completed"}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook(body, sig, secret), "valid signature must pass"
        assert verify_webhook(body, sig.upper(), secret), "hex compare is case-insensitive"
        assert not verify_webhook(body + b" ", sig, secret), "tampered body must fail"
        assert not verify_webhook(body, sig, "wrong"), "wrong secret must fail"
        assert not verify_webhook(body, "", secret), "missing signature must fail"
        assert not verify_webhook(b"", sig, secret), "empty body must fail"
    check("webhook: HMAC passes valid, fails tampered/wrong/empty", t_webhook)

    # 7. webhook envelope parsing
    def t_envelope():
        parsed = parse_webhook(b'{"event":"company_ein_issued","eventPayload":{"doolaCompanyId":"c1"}}')
        assert parsed["event"] == "company_ein_issued" and parsed["known"]
        parsed = parse_webhook(b'{"event":"partner_webhook_disabled","eventPayload":null}')
        assert parsed["known"] and parsed["eventPayload"] is None
        assert not parse_webhook(b'{"event":"something_new","eventPayload":{}}')["known"]
    check("webhook: envelope parsed, unknown events flagged", t_envelope)

    # 8. redaction -- the secret rule
    def t_redact():
        payload = {"firstName": "Jane", "ssn": "123-45-6789",
                   "members": [{"taxId": "987654321", "note": "ssn 111-22-3333"}]}
        out = redact(payload)
        blob = json.dumps(out)
        assert "123-45-6789" not in blob
        assert "987654321" not in blob
        assert "111-22-3333" not in blob
        assert out["firstName"] == "Jane", "non-secret fields survive"
        assert payload["ssn"] == "123-45-6789", "redact must not mutate the input"
    check("redact: SSN/ITIN masked, input untouched", t_redact)

    # 9. leak refusal
    def t_leak():
        assert_no_secret_leak("no secrets here")
        try:
            assert_no_secret_leak("member ssn 123-45-6789")
            raise AssertionError("should have refused")
        except SecretRefused:
            pass
    check("guard: SSN-shaped text refused before publish", t_leak)

    # 10. error branching
    def t_errors():
        assert DoolaError("E_IDEMPOTENCY_KEY_REUSED", "x", 409).is_idempotency_conflict()
        assert DoolaError("E_IDEMPOTENCY_IN_PROGRESS", "x", 409).is_idempotency_conflict()
        assert DoolaError("E_HTTP", "x", 503).is_retryable()
        assert not DoolaError("E_VALIDATION", "x", 422).is_retryable()
    check("errors: branch on code without parsing strings", t_errors)

    # 11. progress reads the two signals separately
    def t_progress():
        company = {
            "formationSubmissionStatus": "SUBMITTED",
            "ein": "88-1234567",
            "services": [{"service": "Formation", "status": "Completed"},
                         {"service": "EinCreation", "status": "Completed"}],
        }
        p = formation_progress(company)
        assert p["formed"] and p["ein"] == "88-1234567"
        # submitted != formed
        p2 = formation_progress({"formationSubmissionStatus": "SUBMITTED", "services": []})
        assert p2["submission"] == "SUBMITTED" and not p2["formed"]
    check("progress: submission status kept distinct from formation", t_progress)

    # 12. expedited EIN shape
    def t_expedite():
        s = expedited_ein_service()
        assert s == {"service": "EinCreation", "variant": "Expedite"}
    check("expedited EIN: documented request shape", t_expedite)

    # 13. no credential may be constructed by this module
    def t_no_literal():
        src = pathlib.Path(__file__).read_text(encoding="utf-8")
        for pattern in (r"dk_live_[A-Za-z0-9]{6,}", r"dk_test_[A-Za-z0-9]{6,}"):
            assert not re.search(pattern, src), "a real-looking key is embedded in source"
    check("custody: no API key literal in this source file", t_no_literal)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, err in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"\n         {err}" if err else ""))
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_status(args) -> int:
    base = resolve_base()
    try:
        key = resolve_api_key()
        key_state = f"present ({key[:8]}..., {len(key)} chars)"
    except DoolaError:
        key_state = "ABSENT"
    try:
        resolve_webhook_secret()
        hook_state = "present"
    except DoolaError:
        hook_state = "ABSENT"
    print("doola -- ae://#startabusiness")
    print(f"  environment   : {'PRODUCTION' if base == PRODUCTION_BASE else 'sandbox'}")
    print(f"  base url      : {base}")
    print(f"  api key       : {key_state}")
    print(f"  webhook secret: {hook_state}")
    print(f"  vault path    : {VAULT_PATH} (exists={VAULT_PATH.exists()})")
    print(f"  key source    : DOOLA_API_KEY env, then vault")
    return 0


def _cmd_selftest(args) -> int:
    print("doola_client selftest -- offline, no credentials, no network\n")
    return selftest()


def _cmd_create_customer(args) -> int:
    client = DoolaClient(allow_production=args.live)
    status, payload = client.create_customer(
        email=args.email, first_name=args.first, last_name=args.last,
        phone_number=args.phone, country_of_residence=args.country,
    )
    print(f"HTTP {status}")
    print(json.dumps(redact(payload), indent=2))
    return 0


def _cmd_create_company(args) -> int:
    client = DoolaClient(allow_production=args.live)
    payload = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    status, out = client.create_company(payload)
    print(f"HTTP {status}")
    print(json.dumps(redact(out), indent=2))
    return 0


def _cmd_get_company(args) -> int:
    client = DoolaClient(allow_production=args.live)
    _, company = client.get_company(args.company_id)
    print(json.dumps(redact(formation_progress(company)), indent=2))
    return 0


def _cmd_verify_webhook(args) -> int:
    body = pathlib.Path(args.body_file).read_bytes()
    ok = verify_webhook(body, args.signature, resolve_webhook_secret())
    print("signature VALID" if ok else "signature INVALID -- reject this delivery")
    return 0 if ok else 1


def _cmd_playbook(args) -> int:
    print("""doola -> ae://#startabusiness -- the wired flow

  1. GATHER     collect founder + company facts locally (never in a chat)
  2. CUSTOMER   POST /v1/partner/customers          -> doolaCustomerId
  3. FORMATION  POST /v1/partner/companies          -> starts the filing
  4. WEBHOOK    verify X-Doola-Signature, react to events; never poll
  5. DOCUMENTS  on document_* -> list + short-lived download URL
  6. RECEIPT    append the formation receipt to kaenbaen

  sandbox first: DOOLA_ENV unset (or sandbox) + a dk_test_ key
  then replay with the playground to fire every webhook on demand""")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doola_client", description=__doc__.splitlines()[1])
    parser.add_argument("--live", action="store_true",
                        help="confirm production (real filings, real money)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show environment and credential presence").set_defaults(fn=_cmd_status)
    sub.add_parser("selftest", help="offline proof, no credentials needed").set_defaults(fn=_cmd_selftest)
    sub.add_parser("playbook", help="print the wired formation flow").set_defaults(fn=_cmd_playbook)

    p = sub.add_parser("create-customer", help="step 2: create a customer")
    p.add_argument("--email", required=True)
    p.add_argument("--first", required=True)
    p.add_argument("--last", required=True)
    p.add_argument("--phone")
    p.add_argument("--country", default="USA")
    p.set_defaults(fn=_cmd_create_customer)

    p = sub.add_parser("create-company", help="step 3: submit a formation")
    p.add_argument("--file", required=True, help="JSON payload")
    p.set_defaults(fn=_cmd_create_company)

    p = sub.add_parser("get-company", help="read formation progress")
    p.add_argument("--company-id", required=True)
    p.set_defaults(fn=_cmd_get_company)

    p = sub.add_parser("verify-webhook", help="check X-Doola-Signature")
    p.add_argument("--body-file", required=True)
    p.add_argument("--signature", required=True)
    p.set_defaults(fn=_cmd_verify_webhook)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except SecretRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except DoolaError as exc:
        print(f"error {exc.code}: {exc.message}", file=sys.stderr)
        if exc.is_idempotency_conflict():
            print("  -> a create already owns this Idempotency-Key; do not invent a new one blindly.",
                  file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

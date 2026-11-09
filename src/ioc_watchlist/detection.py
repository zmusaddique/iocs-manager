"""IOC type detection.

Supported types: ipv4, domain, url, md5, sha1, sha256.

Defanged values are normalized first with ioc-fanger, so entries like
``1.2.3[.]4`` or ``hxxp://evil[.]com/x`` are accepted and stored in their
fanged form.

Chunked/defanged hashes are also recovered: ``d41d8cd9 8f00b204 ...``,
``d41d-8cd9-...`` and ``...ecf8[4]27e`` detect as md5/sha1/sha256 and are
stored as the plain fanged hex string.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from ioc_fanger import fang
from url_normalize import url_normalize

IOC_TYPES = ("ipv4", "domain", "url", "md5", "sha1", "sha256")

URL_SCHEMES = {"http", "https", "ftp"}

HASH_RES = {
    "md5": re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE),
    "sha1": re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE),
    "sha256": re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE),
}

# Hash chunk delimiters used in threat feeds and chat logs:
#   "d41d8cd9 8f00b204 ..." (spaces / newlines)
#   "d41d-8cd9-..."         (hyphenated)
#   "...ecf8[4]27e"         (bracketed hex chunks, any bracket style)
_HEX_CHUNK = re.compile(r"[\[\(\{]([0-9a-fA-F]+)[\]\)\}]")
_HASH_DELIMITERS = re.compile(r"[\s-]+")


def _fanged_hash(value: str) -> str | None:
    """Recover a chunked/defanged hash from `value`, or None.

    Only engages when, after stripping feed-style delimiters, the result is a
    pure-hex string of md5/sha1/sha256 length — so hyphens in domains and URLs
    ('a-b.com', '/deliver-y/x') can never be touched.
    """
    candidate = _HEX_CHUNK.sub(r"\1", value)
    candidate = _HASH_DELIMITERS.sub("", candidate)
    if any(pattern.match(candidate) for pattern in HASH_RES.values()):
        return candidate
    return None


# A hostname/domain label: alphanumeric or hyphen, no leading/trailing hyphen.
LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)


class InvalidIOCError(ValueError):
    def __init__(self, value: str, reason: str):
        super().__init__(reason)
        self.value = value
        self.reason = reason


def normalize_value(raw: str) -> str:
    """Strip whitespace and 'fang' (un-defang) the value."""
    return fang(raw.strip())


def _valid_labels(host: str) -> bool:
    """True if `host` is a dot-separated hostname whose labels are valid."""
    host = host.rstrip(".")
    if not host or len(host) > 253:
        return False
    return all(LABEL_RE.match(label) for label in host.split("."))


def _looks_like_ipv4(host: str) -> bool:
    try:
        ipaddress.IPv4Address(host)
        return True
    except ValueError:
        return False


def _detect_url(value: str) -> str | None:
    """Return a canonical URL, or None if `value` is not a URL.

    Raises InvalidIOCError when the value *looks* like a URL (it has an
    http/https/ftp scheme) but is otherwise malformed.
    """
    split = urlsplit(value)
    if split.scheme not in URL_SCHEMES:
        return None

    host = split.hostname
    if not host:
        raise InvalidIOCError(value, "URL has no hostname")

    if not (_valid_labels(host) or _looks_like_ipv4(host)):
        raise InvalidIOCError(value, f"URL hostname {host!r} is invalid")

    try:
        split.port  # raises ValueError on an invalid port
    except ValueError as exc:
        raise InvalidIOCError(value, f"URL has an invalid port: {exc}") from exc

    return url_normalize(value)


URL_SCHEME_DISPLAY = {"http": "hxxp", "https": "hxxps", "ftp": "ftp"}


def defang_for_display(canonical: str, ioc_type: str) -> str:
    """Re-defang a canonical IOC value for safe display in listings.

    - ipv4 / domain: dots become "[.]"  (8[.]8[.]8[.]8, evil[.]com)
    - url: scheme becomes hxxp / hxxps (ftp keeps its scheme) and every dot
      in the rest of the URL (host, path, query) becomes "[.]"; port,
      userinfo and punctuation are preserved.
    - md5 / sha1 / sha256: "re-defanging" a pure-hex hash defangs nothing
      meaningful, so it is re-chunked into 8-char blocks joined with
      hyphens (d41d8cd9-8f00b204-...), matching how chunked hashes are
      written in feeds.
    """
    if ioc_type in ("md5", "sha1", "sha256"):
        return "-".join(
            canonical[i : i + 8] for i in range(0, len(canonical), 8)
        )

    if ioc_type == "url":
        scheme, _, rest = canonical.partition("://")
        return (
            URL_SCHEME_DISPLAY.get(scheme, scheme)
            + "://"
            + rest.replace(".", "[.]")
        )

    return canonical.replace(".", "[.]")


def detect(raw: str) -> tuple[str, str]:
    """Detect the IOC type of `raw`.

    Returns (type, normalized_value). Raises InvalidIOCError when the value
    matches no supported type.
    """
    value = normalize_value(raw)
    if not value:
        raise InvalidIOCError(raw, "Value is empty")
    if len(value) > 2048:
        raise InvalidIOCError(raw, "Value is too long")

    # Hashes: fixed-length hex strings. Checked first so they can never be
    # mistaken for something else. Chunked/defanged hashes are recovered
    # here (feed-style delimiters are stripped, result must be pure hex).
    hash_value = _fanged_hash(value) or value
    for ioc_type, pattern in HASH_RES.items():
        if pattern.match(hash_value):
            return ioc_type, hash_value.lower()

    # URL: has an http/https/ftp scheme (defanged schemes are fanged above).
    url = _detect_url(value)
    if url is not None:
        return "url", url

    # IPv4 address (rejects leading zeros, e.g. 01.2.3.4).
    if _looks_like_ipv4(value):
        return "ipv4", value

    # Domain: valid labels, at least two, alphabetic TLD.
    host = value.rstrip(".").lower()
    labels = host.split(".")
    if (
        len(labels) >= 2
        and _valid_labels(host)
        and labels[-1].isalpha()
    ):
        return "domain", host

    raise InvalidIOCError(
        value,
        "not a valid ipv4, domain, url, md5, sha1 or sha256",
    )

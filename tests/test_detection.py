"""Unit tests for the IOC type-detection business logic (detection.py)."""

import pytest

from ioc_watchlist.detection import (
    IOC_TYPES,
    InvalidIOCError,
    detect,
    normalize_value,
)

from helpers import VALID_MD5, VALID_SHA1, VALID_SHA256

# (raw_input, expected_type, expected_normalized_value)
VALID_CASES = [
    # -- ipv4 ---------------------------------------------------------------
    ("8.8.8.8", "ipv4", "8.8.8.8"),
    ("0.0.0.0", "ipv4", "0.0.0.0"),
    ("255.255.255.255", "ipv4", "255.255.255.255"),
    ("192.168.10.1", "ipv4", "192.168.10.1"),
    ("  1.2.3.4  ", "ipv4", "1.2.3.4"),  # surrounding whitespace stripped
    ("1.2.3[.]4", "ipv4", "1.2.3.4"),  # defanged
    ("1(.)2(.)3(.)4", "ipv4", "1.2.3.4"),  # alternate defang form
    # -- domain -------------------------------------------------------------
    ("evil.com", "domain", "evil.com"),
    ("evil[.]com", "domain", "evil.com"),
    ("evil[dot]com", "domain", "evil.com"),
    ("sub.domain.example.co.uk", "domain", "sub.domain.example.co.uk"),
    ("UPPER.COM", "domain", "upper.com"),  # lowercased
    ("Example.COM.", "domain", "example.com"),  # trailing dot dropped
    ("a-b.c-d.example.com", "domain", "a-b.c-d.example.com"),
    ("xn--80ak6aa92e.com", "domain", "xn--80ak6aa92e.com"),  # punycode
    # -- url ----------------------------------------------------------------
    ("http://evil.com", "url", "http://evil.com/"),  # trailing slash added
    ("hxxp://bad[.]site/x?p=1", "url", "http://bad.site/x?p=1"),
    ("HTTPS://EXAMPLE.com:443/", "url", "https://example.com/"),  # default
    ("https://evil.com:8443/P?Q=1#F", "url", "https://evil.com:8443/P?Q=1#F"),
    ("http://8.8.8.8/dns-query", "url", "http://8.8.8.8/dns-query"),
    ("http://8.8.8.8:80/x", "url", "http://8.8.8.8/x"),  # default port
    ("ftp://files.example.com:21/pub/f.csv", "url",
     "ftp://files.example.com/pub/f.csv"),
    ("http://evil.com:8080", "url", "http://evil.com:8080/"),  # custom port
    ("http://user@evil.com/", "url", "http://user@evil.com/"),  # userinfo
    # NB: ioc-fanger rewrites 'http:///path' -> 'http://path' (it strips the
    # empty authority), so this arrives as a normal single-label-host URL.
    ("http:///path", "url", "http://path/"),
    ("http://localhost/gate", "url", "http://localhost/gate"),
    # -- hashes (case-normalized to lowercase) ------------------------------
    (VALID_MD5, "md5", VALID_MD5),
    (VALID_MD5.upper(), "md5", VALID_MD5),
    (VALID_SHA1, "sha1", VALID_SHA1),
    ("D41D8CD98F00B204E9800998ECF8427E" + "B920EAA2", "sha1",
     "d41d8cd98f00b204e9800998ecf8427e" + "b920eaa2"),
    (VALID_SHA256, "sha256", VALID_SHA256),
    (VALID_SHA256.upper(), "sha256", VALID_SHA256),
    ("a" * 64, "sha256", "a" * 64),
    # -- chunked/defangled hashes (threat-feed & chat-log formats) ----------
    ("d41d8cd9 8f00b204 e9800998 ecf8427e", "md5", VALID_MD5),
    ("D41D8CD9 8F00B204 E9800998 ECF8427E", "md5", VALID_MD5),
    ("d41d-8cd9-8f00-b204-e980-0998-ecf8-427e", "md5", VALID_MD5),
    ("d41d8cd98f00b204e9800998ecf84[2]7e", "md5", VALID_MD5),
    ("d41d8cd98f00b204e9800998ecf8(4)27e", "md5", VALID_MD5),
    ("[d41d8cd98f00b204e9800998ecf8427e]", "md5", VALID_MD5),
    ("2b2b2b2b 2b2b2b2b 2b2b2b2b 2b2b2b2b 2b2b2b2b", "sha1", VALID_SHA1),
    ("2b2b2b2b-2b2b2b2b-2b2b2b2b-2b2b2b2b-2b2b2b2b", "sha1", VALID_SHA1),
    ("308940cd e82f58f2 1d3d80d0 d16f23b8 e5d1cb2c e9a6b0a5 e64b3d13 a58f2c19",
     "sha256", VALID_SHA256),
    ("308940cd-e82f58f2-1d3d80d0-d16f23b8-e5d1cb2c-e9a6b0a5-e64b3d13-a58f2c19",
     "sha256", VALID_SHA256),
    (VALID_SHA256.replace("23b8e", "23b8[e]"), "sha256", VALID_SHA256),
]

INVALID_CASES = [
    # empty / whitespace
    "",
    "   ",
    "\t\n",
    # failed ipv4s
    "1.2.3",  # missing octet
    "999.1.2.3",  # octet out of range
    "01.02.03.04",  # leading zeros
    "1.2.3.4.5",  # too many octets
    "1.2.3.4/24",  # not a bare address
    "1 . 2.3.4",  # embedded whitespace
    "1.2.3.4.",  # trailing dot makes it neither ipv4 nor a domain
    # wrong length or charset for the hash types
    "deadbeef",  # too short
    "e" * 32 + "f",  # 33 chars: not md5/sha1/sha256
    "e" * 64 + "f",  # 65 chars
    "g" * 64,  # right length, not hexadecimal
    # intermediate off-by-one boundary lengths must not match a loose regex
    "e" * 31,  # one character under md5
    "e" * 39,  # one character under sha1
    "e" * 63,  # one character under sha256
    # chunk-delimiting that does not recover a hash
    "d41d8cd9 8f00b204",  # chunked, but only 16 hex chars after joining
    "d41d 8cd9",  # chunked, still far too short
    "d41d8cd9, 8f00b204, e9800998, ecf8427e",  # commas are not feed
    # separators; a comma-list of hashes is not a single hash
    # failed domains
    "localhost",  # single label, no TLD
    "3.14",  # numeric TLD, no alpha TLD
    "-leadinghyphen.com",
    "trailinghyphen-.com",
    "double..dot.com",  # empty label
    "a" * 64 + ".com",  # first label too long (> 63)
    "münchen.de",  # non-ASCII host (no punycode auto-encoding)
    "bad domain.com",  # whitespace inside
    "user[at]example.com",  # fangs to user@example.com, still invalid
    # urls that are structurally broken (look like URLs, so they error clear)
    "http://",  # no hostname even after fanging
    "http://bad host.com",  # whitespace in host
    "http://-bad.com",  # invalid label
    "http://evil.com:99999/x",  # port out of range
    # unsupported / exotic schemes
    "gopher://a.com",
    "javascript:alert(1)",
    "mailto:a@b.com",
    "file:///etc/passwd",
    # other junk
    "123",
    "not an ioc!!!",
    "::1",
    "[::1]",  # fanger leaves untouched; ipv6 unsupported
    "C:\\Windows\\System32",
    "a" * 2049,  # over the 2048 length cap
]


class TestDetect:
    @pytest.mark.parametrize(("raw", "expected_type", "expected"),
                             VALID_CASES)
    def test_valid_values(self, raw, expected_type, expected):
        detected_type, normalized = detect(raw)
        assert detected_type == expected_type
        assert normalized == expected
        assert detected_type in IOC_TYPES

    @pytest.mark.parametrize("raw", INVALID_CASES)
    def test_invalid_values_raise(self, raw):
        with pytest.raises(InvalidIOCError):
            detect(raw)

    def test_supported_types_match_business_list(self):
        assert set(IOC_TYPES) == {
            "ipv4", "domain", "url", "md5", "sha1", "sha256"
        }


class TestFangedHashes:
    """Chunked hashes must behave exactly like their clean fanged form: same
    type, same stored value — which is also what makes duplicate-rejection
    (value-based UNIQUE) work across defang styles."""

    CHUNK_PAIRS = [
        (VALID_MD5, "d41d8cd9 8f00b204 e9800998 ecf8427e"),
        (VALID_MD5, "d41d-8cd9-8f00-b204-e980-0998-ecf8-427e"),
        (VALID_MD5, "d41d8cd98f00b204e9800998ecf84[2]7e"),
        (VALID_SHA1, "2b2b2b2b-2b2b2b2b-2b2b2b2b-2b2b2b2b-2b2b2b2b"),
        (
            VALID_SHA256,
            "308940cd e82f58f2 1d3d80d0 d16f23b8 e5d1cb2c e9a6b0a5 "
            "e64b3d13 a58f2c19",
        ),
    ]

    @pytest.mark.parametrize(("clean", "defanged"), CHUNK_PAIRS)
    def test_chunked_detects_as_clean_hash(self, clean, defanged):
        detected_type, normalized = detect(defanged)
        assert detected_type == detect(clean)[0]
        assert normalized == clean  # stored clean -> dedup works

        # fang-and-chunk-recovery is idempotent: re-feeding the clean hash
        # gives the identical outcome
        assert detect(normalized) == (detected_type, normalized)

    @pytest.mark.parametrize("hyphenated_ioc", [
        "a-b-c-d.example.com",  # domain
        "http://evil.com/deliver-y/x",  # url path
    ])
    def test_hyphens_outside_hash_context_untouched(self, hyphenated_ioc):
        detected_type, normalized = detect(hyphenated_ioc)
        assert detected_type in ("domain", "url")
        assert normalized == hyphenated_ioc


class TestInvalidIOCError:
    def test_carries_value_and_reason(self):
        with pytest.raises(InvalidIOCError) as excinfo:
            detect("not an ioc!!!")
        error = excinfo.value
        assert error.value == "not an ioc!!!"
        assert "not a valid ipv4, domain, url, md5, sha1 or sha256" \
            in error.reason

    def test_empty_value_reason(self):
        with pytest.raises(InvalidIOCError) as excinfo:
            detect("   ")
        assert excinfo.value.reason == "Value is empty"

    def test_too_long_value_reason(self):
        with pytest.raises(InvalidIOCError) as excinfo:
            detect("a" * 2049)
        assert excinfo.value.reason == "Value is too long"

    def test_missing_url_hostname_reason(self):
        with pytest.raises(InvalidIOCError) as excinfo:
            detect("http://")
        assert "no hostname" in excinfo.value.reason


class TestNormalizeValue:
    @pytest.mark.parametrize(("raw", "expected"), [
        ("  evil.com  ", "evil.com"),
        ("1.2.3[.]4", "1.2.3.4"),
        ("evil[dot]com", "evil.com"),
        ("hxxps://evil.com", "https://evil.com"),
        ("bad.com", "bad.com"),  # already clean, unchanged
        ("[::1]", "[::1]"),  # fanger leaves it alone
        # ioc-fanger has no hash awareness: chunking is recovered by
        # detect(), not by fanging, and passes through here verbatim
        ("d41d8cd9 8f00b204 e9800998 ecf8427e",
         "d41d8cd9 8f00b204 e9800998 ecf8427e"),
        ("d41d-8cd9-8f00-b204-e980-0998-ecf8-427e",
         "d41d-8cd9-8f00-b204-e980-0998-ecf8-427e"),
        ("d41d8cd98f00b204e9800998ecf84[2]7e",
         "d41d8cd98f00b204e9800998ecf84[2]7e"),
    ])
    def test_fang_and_strip(self, raw, expected):
        assert normalize_value(raw) == expected

    def test_is_idempotent_on_clean_input(self):
        for value in ("8.8.8.8", "evil.com", VALID_MD5):
            assert normalize_value(normalize_value(value)) == normalize_value(
                value
            )

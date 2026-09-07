"""
Sprint 6 — Data pipeline security

Every JSON payload gets a SHA-256 checksum computed over its canonical
(sorted-key) serialization before it's stored. The checksum travels with the
object so any consumer can re-hash and verify the payload wasn't corrupted
or tampered with in transit/at rest.
"""
import hashlib
import json


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_checksum(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_checksum(payload: dict, expected_checksum: str) -> bool:
    return sha256_checksum(payload) == expected_checksum

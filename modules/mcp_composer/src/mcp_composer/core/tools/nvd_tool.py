import os
import asyncio
import csv
import re
import logging
from io import StringIO
from typing import Any

import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# NVD CVE API 2.0 base URL :contentReference[oaicite:4]{index=4}
NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Optional API key (recommended for higher rate limits) :contentReference[oaicite:5]{index=5}
NVD_API_KEY = os.getenv("NVD_API_KEY")

# NVD suggests sleeping between requests in scripted workflows :contentReference[oaicite:6]{index=6}
# Default to 6s (safe without a key); with a key you can lower this if you like.
DEFAULT_DELAY_SECONDS = float(
    os.getenv("NVD_REQUEST_DELAY_SECONDS", "6.0" if not NVD_API_KEY else "0.7")
)

# Batch processing configuration for large CSV files
BATCH_SIZE = int(os.getenv("NVD_BATCH_SIZE", "50"))  # Process CVEs in batches
MAX_CONCURRENT_REQUESTS = int(
    os.getenv("NVD_MAX_CONCURRENT", "5")
)  # Concurrent API calls


# Basic CVSS bucket thresholds (v3.x convention)
def score_to_severity(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score == 0.0:
        return "NONE"
    if 0.0 < score <= 3.9:
        return "LOW"
    if 4.0 <= score <= 6.9:
        return "MEDIUM"
    if 7.0 <= score <= 8.9:
        return "HIGH"
    if 9.0 <= score <= 10.0:
        return "CRITICAL"
    return "UNKNOWN"


def _get_first_metric(
    metrics: dict[str, Any], keys_in_preference: list[str]
) -> dict[str, Any] | None:
    """
    NVD typically includes one of:
      - cvssMetricV31 / cvssMetricV30
      - cvssMetricV40
      - cvssMetricV2
    Each is usually a list; we take the first entry.
    """
    for k in keys_in_preference:
        v = metrics.get(k)
        if isinstance(v, list) and v:
            first = v[0]
            if isinstance(first, dict):
                return first
    return None


def extract_best_cvss(
    cve: dict[str, Any],
) -> tuple[float | None, str | None, str | None]:
    """
    Returns (score, severity_label_if_present, version_used)
    - Prefer CVSS v3.1 then v3.0
    - Else try CVSS v4.0
    - Else fallback to CVSS v2
    """
    metrics = cve.get("metrics") or {}
    if not isinstance(metrics, dict):
        return None, None, None

    # Prefer v3.1 then v3.0, then v4.0, then v2
    preferred = _get_first_metric(metrics, ["cvssMetricV31", "cvssMetricV30"])
    if preferred:
        data = preferred.get("cvssData") or {}
        score = data.get("baseScore")
        sev = data.get("baseSeverity")  # often present for v3
        return (
            (float(score) if score is not None else None),
            (str(sev) if sev else None),
            ("3.1" if "cvssMetricV31" in metrics else "3.0"),
        )

    v4 = _get_first_metric(metrics, ["cvssMetricV40"])
    if v4:
        data = v4.get("cvssData") or {}
        score = data.get("baseScore")
        sev = data.get("baseSeverity")  # may exist
        return (
            (float(score) if score is not None else None),
            (str(sev) if sev else None),
            "4.0",
        )

    v2 = _get_first_metric(metrics, ["cvssMetricV2"])
    if v2:
        data = v2.get("cvssData") or {}
        score = data.get("baseScore")
        # CVSSv2 doesn't always include a "baseSeverity" field the same way
        return (float(score) if score is not None else None), None, "2.0"

    return None, None, None


async def nvd_get(params: dict[str, Any]) -> dict[str, Any]:
    headers = {}
    if NVD_API_KEY:
        headers["apiKey"] = (
            NVD_API_KEY  # apiKey header :contentReference[oaicite:7]{index=7}
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(NVD_CVE_API, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_cve_by_id(cve_id: str) -> dict[str, Any]:
    # cveId parameter :contentReference[oaicite:8]{index=8}
    data = await nvd_get({"cveId": cve_id})
    await asyncio.sleep(DEFAULT_DELAY_SECONDS)
    return data


async def _fetch_single_cve(cve_id: str) -> tuple[str, dict[str, Any]]:
    """Fetch and process a single CVE. Returns (cve_id, result_dict)."""
    try:
        payload = await fetch_cve_by_id(cve_id)
        vulns = payload.get("vulnerabilities") or []
        if not vulns:
            return cve_id, {
                "severity": "UNKNOWN",
                "reason": "Not found in NVD response",
            }

        cve = vulns[0].get("cve") or {}
        score, sev_label, version = extract_best_cvss(cve)

        severity = (
            sev_label.upper() if isinstance(sev_label, str) else None
        ) or score_to_severity(score)

        return cve_id, {
            "severity": severity,
            "cvss_base_score": score,
            "cvss_version": version,
            "source": "NVD",
        }

    except httpx.HTTPStatusError as e:
        return cve_id, {
            "severity": "UNKNOWN",
            "error": f"HTTP error from NVD: {e.response.status_code}",
        }
    except Exception as e:
        return cve_id, {"severity": "UNKNOWN", "error": str(e)}


async def classify_cves(cve_ids: list[str]) -> dict[str, Any]:
    """
    Classify a set of CVE IDs into severity categories using NVD CVE API 2.0.
    Optimized for large batches with concurrent processing and rate limiting.

    Returns:
      - per_cve: mapping of CVE -> classification detail
      - summary: counts per category
    """
    results: dict[str, Any] = {}
    summary = {"NONE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "UNKNOWN": 0}

    total_cves = len(cve_ids)
    if total_cves == 0:
        return {"per_cve": results, "summary": summary}

    logger.info(f"Starting classification of {total_cves} CVEs")

    # Process CVEs with controlled concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _fetch_with_semaphore(cve_id: str) -> tuple[str, dict[str, Any]]:
        async with semaphore:
            return await _fetch_single_cve(cve_id)

    # Process in batches to avoid memory issues and provide progress updates
    for batch_start in range(0, total_cves, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_cves)
        batch = cve_ids[batch_start:batch_end]

        logger.info(
            f"Processing CVE batch {batch_start + 1}-{batch_end} of {total_cves}"
        )

        # Fetch batch concurrently
        batch_results = await asyncio.gather(
            *[_fetch_with_semaphore(cve_id) for cve_id in batch], return_exceptions=True
        )

        # Process results
        for result in batch_results:
            if isinstance(result, (Exception, BaseException)):
                logger.error(f"Unexpected error in batch processing: {result}")
                continue

            cve_id, detail = result
            results[cve_id] = detail
            severity = detail.get("severity", "UNKNOWN")
            summary[severity] = summary.get(severity, 0) + 1

    logger.info(f"Completed classification: {summary}")
    return {"per_cve": results, "summary": summary}


async def list_cves_by_cvss_v3_severity(
    severity: str,
    results_per_page: int = 20,
    start_index: int = 0,
) -> dict[str, Any]:
    """
    Demonstrates using NVD query parameter:
      ?cvssV3Severity=LOW  (or MEDIUM/HIGH/CRITICAL)

    Returns a page of CVE IDs plus paging metadata.
    """
    sev = severity.strip().upper()
    params = {
        "cvssV3Severity": sev,
        "resultsPerPage": results_per_page,
        "startIndex": start_index,
        "noRejected": "",  # exclude rejected if you want (presence-based flag) :contentReference[oaicite:9]{index=9}
    }

    data = await nvd_get(params)
    await asyncio.sleep(DEFAULT_DELAY_SECONDS)

    cve_ids: list[str] = []
    for v in data.get("vulnerabilities") or []:
        c = v.get("cve") or {}
        cid = c.get("id")
        if cid:
            cve_ids.append(cid)

    return {
        "query": {
            "cvssV3Severity": sev,
            "resultsPerPage": results_per_page,
            "startIndex": start_index,
        },
        "resultsPerPage": data.get("resultsPerPage"),
        "startIndex": data.get("startIndex"),
        "totalResults": data.get("totalResults"),
        "cve_ids": cve_ids,
    }


_CVE_ID_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE", "UNKNOWN"]


def _extract_cve_id_from_row(row: dict[str, Any]) -> str | None:
    """Find the first CVE ID in any value of a CSV row."""
    for value in row.values():
        if value is None:
            continue
        match = _CVE_ID_RE.search(str(value))
        if match:
            return match.group(0).upper()
    return None


async def enrich_issues_csv_with_cvss(csv_text: str) -> str:
    """
    Parse issues CSV, fetch CVSS scores for CVE IDs, add columns, and sort rows.
    Optimized for large CSV files (2-3MB) with batching and progress logging.

    Adds columns:
      - cvss_score
      - cvss_severity
    Sort order: CRITICAL, HIGH, MEDIUM, LOW, NONE, UNKNOWN
    """
    logger.info(f"Starting CSV enrichment (size: {len(csv_text)} bytes)")

    input_io = StringIO(csv_text)
    reader = csv.DictReader(input_io)
    rows = [row for row in reader]

    if not rows:
        logger.info("Empty CSV, returning as-is")
        return csv_text

    row_count = len(rows)
    logger.info(f"Processing {row_count} rows")

    # Extract unique CVE IDs efficiently
    cve_ids_set = set()
    for row in rows:
        cve = _extract_cve_id_from_row(row)
        if cve:
            cve_ids_set.add(cve)

    cve_ids = sorted(cve_ids_set)
    unique_cve_count = len(cve_ids)
    logger.info(f"Found {unique_cve_count} unique CVE IDs")

    # Fetch CVSS info for CVE IDs (with batching and concurrency control)
    cvss_map: dict[str, dict[str, Any]] = {}
    if cve_ids:
        classified = await classify_cves(cve_ids)
        per_cve = classified.get("per_cve", {})
        for cve_id, detail in per_cve.items():
            cvss_map[cve_id.upper()] = detail

    # Add columns to rows
    logger.info("Enriching rows with CVSS data")
    for idx, row in enumerate(rows):
        if idx % 500 == 0 and idx > 0:
            logger.info(f"Enriched {idx}/{row_count} rows")

        cve_id = _extract_cve_id_from_row(row)
        if cve_id and cve_id in cvss_map:
            detail = cvss_map[cve_id]
            row["cvss_score"] = detail.get("cvss_base_score")
            row["cvss_severity"] = detail.get("severity")
        else:
            row["cvss_score"] = None
            row["cvss_severity"] = "UNKNOWN"

    # Sort rows by severity order
    logger.info("Sorting rows by severity")

    def _severity_rank(row: dict[str, Any]) -> int:
        sev = str(row.get("cvss_severity") or "UNKNOWN").upper()
        return (
            _SEVERITY_ORDER.index(sev)
            if sev in _SEVERITY_ORDER
            else len(_SEVERITY_ORDER)
        )

    rows.sort(key=_severity_rank)

    # Write updated CSV
    logger.info("Writing enriched CSV output")
    fieldnames = list(reader.fieldnames or [])
    for extra in ["cvss_score", "cvss_severity"]:
        if extra not in fieldnames:
            fieldnames.append(extra)

    output_io = StringIO()
    writer = csv.DictWriter(output_io, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return output_io.getvalue()

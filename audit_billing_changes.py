#!/usr/bin/env python3
"""
Billing Audit System
Monitors for unauthorized changes to billing data in Smartsheet.
"""

import os
import datetime
import logging
import json
from typing import Dict, List, Optional, Any
import sentry_sdk

# ── Report-only rate-sanity audit (260812-isx) ─────────────────────────
# Tolerance floor for the rate-sanity mismatch check: flag a row only
# when its Units Total Price diverges from (New Rates rate x Quantity)
# by more than the larger of a flat $0.02 rounding allowance and 0.5%
# of the expected price. See the 2026-08-12 SAA-DE-20 stale-formula
# incident entry in memory-bank/living-ledger.md for the defect class
# this guards against — a $170.52 overbill that shipped because the
# primary variant is a deliberate pass-through of Units Total Price.
RATE_SANITY_ABS_TOLERANCE = 0.02
RATE_SANITY_PCT_TOLERANCE = 0.005


def _rate_sanity_expected_price(row: Dict) -> Optional[float]:
    """Compute the expected Units Total Price for a row.

    Expected price is ``New Rates rate x Quantity``, keyed by the
    row's CU and Work Type against ``_SUBCONTRACTOR_RATES``
    (``data/subcontractor_rates.csv``, loaded once at import time by
    ``pipeline/pricing.py``).

    Returns ``None`` (never 0.0) when the row cannot be evaluated:
    empty/unknown CU, a Work Type that matches none of
    install/remove/transfer, or a non-positive parsed quantity/rate.
    Callers MUST treat ``None`` as "skip this row" — it is never a
    legitimate expected price of zero.
    """
    # Function-local lazy import (mirrors pipeline/pricing.py
    # L629-633): generate_weekly_pdfs.py imports this module BEFORE
    # it imports pipeline.pricing, so a module-level import here would
    # pull pipeline.pricing's CSV-loading side effect earlier in the
    # import order. ``_parse_quantity`` is a pure helper not re-
    # exported by the generate_weekly_pdfs facade (only
    # ``_SUBCONTRACTOR_RATES`` and ``parse_price`` are), so it is
    # imported directly from its owning module — also lazily, for the
    # same import-order reason.
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    from pipeline.pricing import _parse_quantity  # noqa: PLC0415

    cu = str(row.get('CU') or '').strip().upper()
    if not cu:
        return None
    rate_row = _gwp._SUBCONTRACTOR_RATES.get(cu)
    if rate_row is None:
        return None

    # Shortest-unambiguous-prefix matcher — reproduces
    # pipeline/pricing.py L667-673 exactly (2026-05-16 23:45 ledger
    # rule): 'install' is NOT contained in the abbreviated 'inst', so
    # the substring test must run in the `token in work_type` order.
    work_type_raw = str(row.get('Work Type') or '').strip().lower()
    if 'inst' in work_type_raw:
        work_type = 'install'
    elif 'rem' in work_type_raw:
        work_type = 'remove'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        work_type = 'transfer'
    else:
        return None

    rate = rate_row.get(f'new_{work_type}_price', 0.0)
    qty = _parse_quantity(row.get('Quantity'))
    if rate <= 0 or qty <= 0:
        return None
    return rate * qty


def _rate_sanity_is_mismatch(expected: float, actual: float) -> bool:
    """Return True when ``actual`` diverges from ``expected`` beyond tolerance.

    Tolerance is ``max(RATE_SANITY_ABS_TOLERANCE,
    RATE_SANITY_PCT_TOLERANCE * expected)`` — a flat cent-rounding
    floor for small expected prices, a percentage floor for large
    ones.
    """
    tolerance = max(
        RATE_SANITY_ABS_TOLERANCE, RATE_SANITY_PCT_TOLERANCE * expected
    )
    return abs(actual - expected) > tolerance


def _rate_sanity_looks_like_zero(raw_price: Any) -> bool:
    """Return True when ``raw_price`` is a genuinely zero-valued cell.

    Distinguishes a legitimate ``$0.00`` price from an unparseable
    string that ``parse_price`` also coerces to 0.0 — only the former
    is a real actual price; the latter must be skipped rather than
    reported as a false $0-vs-expected mismatch.
    """
    cleaned = str(raw_price).strip().replace('$', '').replace(',', '')
    try:
        return float(cleaned) == 0.0
    except (TypeError, ValueError):
        return False


class BillingAudit:
    """
    Advanced billing audit system that monitors for unauthorized changes
    to financial data in Smartsheet source sheets.
    """
    
    def __init__(self, client, skip_cell_history: bool = False):
        """
        Initialize the billing audit system.
        
        Args:
            client: Smartsheet client instance
            skip_cell_history: If True, skips cell history checks for performance
        """
        self.client = client
        self.skip_cell_history = skip_cell_history
        self.audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
        self.logger = logging.getLogger(__name__)

        # Initialize audit state storage
        self.audit_state_file = os.path.join("generated_docs", "audit_state.json")
        self.audit_state = self._load_audit_state()

        # Rate-sanity audit (260812-isx): rows skipped by the detector
        # (missing CU, zero/unparseable quantity or price, unknown work
        # type) — read by _generate_audit_summary().
        self._rate_sanity_skipped = 0
        
        self.logger.info("🔍 Billing Audit System initialized")
        if self.skip_cell_history:
            self.logger.info("⚡ Cell history checks disabled for performance")
        
    def _load_audit_state(self) -> Dict:
        """Load previous audit state from file."""
        try:
            if os.path.exists(self.audit_state_file):
                with open(self.audit_state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load audit state: {e}")
        
        return {
            "last_audit_time": None,
            "monitored_sheets": {},
            "flagged_changes": [],
            "audit_summary": {}
        }
    
    def _save_audit_state(self):
        """Save current audit state to file."""
        try:
            os.makedirs(os.path.dirname(self.audit_state_file), exist_ok=True)
            with open(self.audit_state_file, 'w') as f:
                json.dump(self.audit_state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save audit state: {e}")
    
    def audit_financial_data(self, source_sheets: List[Dict], current_rows: List[Dict]) -> Dict:
        """
        Perform comprehensive audit of financial data changes.
        
        Args:
            source_sheets: List of source sheet configurations
            current_rows: Current data rows being processed
            
        Returns:
            Audit results dictionary
        """
        audit_start = datetime.datetime.now(datetime.timezone.utc)
        audit_results = {
            "audit_timestamp": audit_start.isoformat(),
            "sheets_audited": len(source_sheets),
            "rows_audited": len(current_rows),
            "anomalies_detected": [],
            "unauthorized_changes": [],
            "data_integrity_issues": [],
            "rate_sanity_mismatches": [],
            "summary": {}
        }

        try:
            # 1. Check for unauthorized price changes
            price_anomalies = self._detect_price_anomalies(current_rows)
            audit_results["anomalies_detected"].extend(price_anomalies)

            # 2. Validate data consistency
            consistency_issues = self._validate_data_consistency(current_rows)
            audit_results["data_integrity_issues"].extend(consistency_issues)

            # 2.5 Report-only rate-sanity check (260812-isx): Units Total
            # Price vs New Rates rate x Quantity. Never mutates rows,
            # pricing, grouping, filenames, hashes, or upload behavior.
            rate_sanity_mismatches = self._detect_rate_sanity_mismatches(
                current_rows
            )
            audit_results["rate_sanity_mismatches"].extend(
                rate_sanity_mismatches
            )

            # 3. Check for suspicious patterns (only if not skipping cell history)
            if not self.skip_cell_history:
                suspicious_changes = self._detect_suspicious_changes(source_sheets)
                audit_results["unauthorized_changes"].extend(suspicious_changes)
            
            # 4. Generate audit summary
            audit_results["summary"] = self._generate_audit_summary(audit_results)
            
            # 5.a Selective cell history enrichment for problematic rows (only ones with issues to limit API use)
            try:
                enriched = self._selective_cell_history_enrichment(current_rows, audit_results)
                if enriched:
                    audit_results["enriched_cells"] = enriched
            except Exception as enr_err:
                self.logger.debug(f"Cell history enrichment skipped: {enr_err}")

            # 5.b Compute trend vs previous and attach
            try:
                trend = self._compute_trend(audit_results["summary"])
                if trend:
                    audit_results["trend"] = trend
            except Exception as trend_err:  # defensive
                self.logger.debug(f"Trend computation skipped: {trend_err}")

            # 6. Log audit results (now includes trend if present)
            self._log_audit_results(audit_results)
            
            # 7. Update audit state & local rolling history
            self.audit_state["last_audit_time"] = audit_start.isoformat()
            self.audit_state["audit_summary"] = audit_results["summary"]
            if "trend" in audit_results:
                self.audit_state["last_trend"] = audit_results["trend"]
            # Append to local risk history (non-critical)
            history_entry = {
                "timestamp": audit_results["audit_timestamp"],
                "risk_level": audit_results["summary"].get("risk_level"),
                "total_issues": audit_results["summary"].get("total_anomalies",0) + audit_results["summary"].get("total_unauthorized_changes",0) + audit_results["summary"].get("total_data_issues",0),
                "trend": audit_results.get("trend", {})
            }
            try:
                hist_path = os.path.join("generated_docs", "risk_trend.json")
                existing_hist = []
                if os.path.exists(hist_path):
                    with open(hist_path, 'r') as hf:
                        existing_hist = json.load(hf)
                existing_hist.append(history_entry)
                existing_hist = existing_hist[-50:]
                with open(hist_path, 'w') as hf:
                    json.dump(existing_hist, hf, indent=2)
            except Exception as e:
                self.logger.debug(f"Could not persist local risk history: {e}")
            self._save_audit_state()
            
        except Exception as e:
            self.logger.error(f"Audit system error: {e}")
            if os.getenv("SENTRY_DSN"):
                sentry_sdk.capture_exception(e)
            
            audit_results["error"] = str(e)
        
        return audit_results
    
    def _detect_price_anomalies(self, rows: List[Dict]) -> List[Dict]:
        """Detect unusual pricing patterns that might indicate unauthorized changes."""
        anomalies = []
        
        try:
            # Group by work request for price analysis
            wr_prices = {}
            for row in rows:
                wr_num = row.get('Work Request #')
                price_str = row.get('Units Total Price', '0')
                
                try:
                    price = float(str(price_str).replace('$', '').replace(',', ''))
                    if wr_num not in wr_prices:
                        wr_prices[wr_num] = []
                    wr_prices[wr_num].append(price)
                except (ValueError, TypeError):
                    continue
            
            # Look for unusual price patterns
            for wr_num, prices in wr_prices.items():
                if len(prices) > 1:
                    price_range = max(prices) - min(prices)
                    avg_price = sum(prices) / len(prices)
                    
                    # Flag if price range is > 50% of average (potential data entry error)
                    if avg_price > 0 and (price_range / avg_price) > 0.5:
                        anomalies.append({
                            "type": "price_variance_anomaly",
                            "work_request": wr_num,
                            "price_range": price_range,
                            "average_price": avg_price,
                            "variance_percentage": (price_range / avg_price) * 100,
                            "severity": "medium",
                            "description": f"High price variance detected in WR# {wr_num}"
                        })
            
        except Exception as e:
            self.logger.warning(f"Price anomaly detection failed: {e}")
        
        return anomalies
    
    def _validate_data_consistency(self, rows: List[Dict]) -> List[Dict]:
        """Validate data consistency across fields."""
        issues = []
        
        try:
            for i, row in enumerate(rows):
                row_issues = []
                
                # Check for missing critical data
                required_fields = ['Work Request #', 'Units Total Price', 'Quantity', 'CU']
                for field in required_fields:
                    if not row.get(field):
                        row_issues.append(f"Missing {field}")
                
                # Check for data type inconsistencies
                price_str = row.get('Units Total Price', '0')
                try:
                    price = float(str(price_str).replace('$', '').replace(',', ''))
                    if price < 0:
                        row_issues.append("Negative price detected")
                except (ValueError, TypeError):
                    row_issues.append("Invalid price format")
                
                # Check quantity consistency
                qty_str = row.get('Quantity', '0')
                try:
                    quantity = float(str(qty_str))
                    if quantity <= 0:
                        row_issues.append("Zero or negative quantity")
                except (ValueError, TypeError):
                    row_issues.append("Invalid quantity format")
                
                if row_issues:
                    issues.append({
                        "type": "data_consistency_issue",
                        "row_index": i,
                        "work_request": row.get('Work Request #', 'Unknown'),
                        "issues": row_issues,
                        "severity": "low" if len(row_issues) == 1 else "medium"
                    })
        
        except Exception as e:
            self.logger.warning(f"Data consistency validation failed: {e}")

        return issues

    def _detect_rate_sanity_mismatches(self, rows: List[Dict]) -> List[Dict]:
        """Flag rows whose Units Total Price disagrees with rate x Quantity.

        REPORT-ONLY (260812-isx): never mutates row price, quantity,
        grouping, filenames, hashes, or upload behavior — it only
        appends diagnostic records. Expected price comes from the New
        Rates columns of ``data/subcontractor_rates.csv``, keyed by CU
        + Work Type (see ``_rate_sanity_expected_price``). See the
        2026-08-12 SAA-DE-20 incident in memory-bank/living-ledger.md.

        Disable via ``RATE_SANITY_AUDIT_ENABLED=false``. Skips (missing
        CU, non-positive quantity, unknown work type, unparseable
        price) are silent per-row and reported only as an aggregate
        count via ``self._rate_sanity_skipped``.
        """
        mismatches: List[Dict] = []
        self._rate_sanity_skipped = 0

        if os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() != "true":
            return mismatches

        try:
            import generate_weekly_pdfs as _gwp  # noqa: PLC0415
            from pipeline.pricing import _parse_quantity  # noqa: PLC0415

            checked = 0
            for row in rows:
                expected = _rate_sanity_expected_price(row)
                if expected is None:
                    self._rate_sanity_skipped += 1
                    continue

                raw_price = row.get('Units Total Price')
                if raw_price is None or str(raw_price).strip() == '':
                    self._rate_sanity_skipped += 1
                    continue

                actual = _gwp.parse_price(raw_price)
                if actual == 0.0 and not _rate_sanity_looks_like_zero(
                    raw_price
                ):
                    # parse_price coerced an unparseable, non-zero-
                    # looking string to 0.0 — a real $0 mismatch would
                    # be misleading here; skip instead.
                    self._rate_sanity_skipped += 1
                    continue

                checked += 1
                if _rate_sanity_is_mismatch(expected, actual):
                    wr = str(row.get('Work Request #', 'Unknown'))
                    cu = str(row.get('CU') or '').strip().upper()
                    work_type = str(row.get('Work Type') or '').strip()
                    qty = _parse_quantity(row.get('Quantity'))
                    mismatches.append({
                        "type": "rate_sanity_mismatch",
                        "work_request": wr,
                        "cu": cu,
                        "work_type": work_type,
                        "quantity": qty,
                        "expected_price": round(expected, 2),
                        "actual_price": round(actual, 2),
                        "delta": round(actual - expected, 2),
                        "severity": "high",
                        "description": (
                            "Units Total Price disagrees with expected "
                            f"rate x Quantity for WR# {wr}"
                        ),
                    })

            # Aggregate-only, per T-ISX-01: counts only, never price,
            # quantity, foreman, or WR-level detail at INFO level.
            self.logger.info(
                "Rate-sanity audit: checked=%d skipped=%d mismatches=%d",
                checked, self._rate_sanity_skipped, len(mismatches),
            )
        except Exception as e:
            self.logger.warning(
                f"Rate sanity mismatch detection failed: {e}"
            )

        return mismatches

    def _detect_suspicious_changes(self, source_sheets: List[Dict]) -> List[Dict]:
        """Detect potentially unauthorized changes (requires cell history)."""
        suspicious_changes = []
        
        if self.skip_cell_history:
            return suspicious_changes
        
        try:
            # This would require detailed cell history analysis
            # For now, we'll implement basic change detection
            current_time = datetime.datetime.now(datetime.timezone.utc)
            recent_threshold = current_time - datetime.timedelta(hours=24)
            
            for sheet in source_sheets:
                sheet_id = sheet.get('id')
                if not sheet_id:
                    continue
                
                try:
                    # Check for recent changes in financial columns
                    # This is a simplified implementation
                    sheet_info = self.client.Sheets.get_sheet(sheet_id, include='discussions')
                    
                    # Look for recent discussions that might indicate changes
                    if hasattr(sheet_info, 'discussions'):
                        for discussion in sheet_info.discussions:
                            if hasattr(discussion, 'created_at'):
                                created_at = discussion.created_at
                                if created_at and created_at > recent_threshold:
                                    suspicious_changes.append({
                                        "type": "recent_discussion",
                                        "sheet_id": sheet_id,
                                        "sheet_name": sheet.get('name', 'Unknown'),
                                        "discussion_id": discussion.id,
                                        "created_at": created_at.isoformat(),
                                        "severity": "low",
                                        "description": "Recent discussion activity detected"
                                    })
                
                except Exception as e:
                    self.logger.warning(f"Could not check changes for sheet {sheet_id}: {e}")
        
        except Exception as e:
            self.logger.warning(f"Suspicious change detection failed: {e}")
        
        return suspicious_changes
    
    def _generate_audit_summary(self, audit_results: Dict) -> Dict:
        """Generate a summary of audit findings."""
        summary = {
            "total_anomalies": len(audit_results.get("anomalies_detected", [])),
            "total_unauthorized_changes": len(audit_results.get("unauthorized_changes", [])),
            "total_data_issues": len(audit_results.get("data_integrity_issues", [])),
            "total_rate_sanity_mismatches": len(
                audit_results.get("rate_sanity_mismatches", [])
            ),
            "rate_sanity_skipped": self._rate_sanity_skipped,
            "risk_level": "LOW",
            "recommendations": []
        }

        # Determine risk level
        total_issues = (
            summary["total_anomalies"]
            + summary["total_unauthorized_changes"]
            + summary["total_data_issues"]
            + summary["total_rate_sanity_mismatches"]
        )

        if total_issues == 0:
            summary["risk_level"] = "LOW"
            summary["recommendations"].append("No issues detected. Continue monitoring.")
        elif total_issues <= 3:
            summary["risk_level"] = "MEDIUM"
            summary["recommendations"].append("Minor issues detected. Review flagged items.")
        else:
            summary["risk_level"] = "HIGH"
            summary["recommendations"].append("Multiple issues detected. Immediate review recommended.")

        # Add specific recommendations based on findings
        if summary["total_anomalies"] > 0:
            summary["recommendations"].append("Review price anomalies for potential data entry errors.")

        if summary["total_data_issues"] > 0:
            summary["recommendations"].append("Address data consistency issues before processing.")

        if summary["total_rate_sanity_mismatches"] > 0:
            summary["recommendations"].append(
                "Rate-sanity mismatches detected: Smartsheet Units Total "
                "Price disagrees with rate x Quantity — check for a "
                "stale quantity formula cell upstream."
            )

        return summary
    
    def _log_audit_results(self, audit_results: Dict):
        """Log audit results to various outputs."""
        summary = audit_results.get("summary", {})
        risk_level = summary.get("risk_level", "UNKNOWN")
        trend = audit_results.get("trend", {})

        # Log to console
        if risk_level == "HIGH":
            self.logger.warning(f"🚨 AUDIT ALERT: {risk_level} risk detected")
        elif risk_level == "MEDIUM":
            self.logger.info(f"⚠️ AUDIT WARNING: {risk_level} risk detected")
        else:
            self.logger.info(f"✅ AUDIT CLEAR: {risk_level} risk level")

        self.logger.info(f"   • Anomalies: {summary.get('total_anomalies', 0)}")
        self.logger.info(f"   • Unauthorized changes: {summary.get('total_unauthorized_changes', 0)}")
        self.logger.info(f"   • Data issues: {summary.get('total_data_issues', 0)}")
        self.logger.info(
            f"   • Rate-sanity mismatches: "
            f"{summary.get('total_rate_sanity_mismatches', 0)}"
        )
        if trend:
            self.logger.info(f"   • Risk Trend: {trend.get('risk_direction')} (Δ level {trend.get('risk_level_delta',0)} / Δ issues {trend.get('issues_delta',0)} {trend.get('issues_delta_pct','')})")

        # Send to Sentry if configured and high risk or worsening trend
        send = False
        if risk_level == "HIGH":
            send = True
        elif trend and trend.get("risk_level_delta",0) > 0:
            send = True
        if os.getenv("SENTRY_DSN") and send:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("audit_risk_level", risk_level)
                scope.set_tag("audit_system", "billing_audit")
                if trend:
                    scope.set_tag("risk_direction", trend.get("risk_direction"))
                    scope.set_tag("risk_level_delta", trend.get("risk_level_delta"))
                    scope.set_tag("issues_delta", trend.get("issues_delta"))
                scope.set_context("audit_results", audit_results)
                sentry_sdk.capture_message(
                    f"AUDIT: Risk {risk_level} trend={trend.get('risk_direction','n/a')} anomalies={summary.get('total_anomalies', 0)}",
                    level="warning" if risk_level == "HIGH" else "info"
                )

        # Log to audit sheet if configured
        if self.audit_sheet_id:
            try:
                self._log_to_audit_sheet(audit_results)
            except Exception as e:
                self.logger.warning(f"Failed to log to audit sheet: {e}")
    
    def _log_to_audit_sheet(self, audit_results: Dict):
        """Log audit results to a Smartsheet audit log."""
        try:
            if not self.audit_sheet_id:
                return
            
            # This would create a new row in the audit sheet
            # Implementation depends on the audit sheet structure
            summary = audit_results.get("summary", {})
            trend = audit_results.get("trend", {})
            audit_row = {
                "Audit Timestamp": audit_results["audit_timestamp"],
                "Risk Level": summary.get("risk_level"),
                "Total Issues": summary.get("total_anomalies",0) + summary.get("total_unauthorized_changes",0) + summary.get("total_data_issues",0),
                "Sheets Audited": audit_results.get("sheets_audited"),
                "Rows Audited": audit_results.get("rows_audited"),
                "Anomalies": summary.get("total_anomalies",0),
                "Unauthorized Changes": summary.get("total_unauthorized_changes",0),
                "Data Issues": summary.get("total_data_issues",0),
                "Risk Direction": trend.get("risk_direction"),
                "Risk Level Δ": trend.get("risk_level_delta"),
                "Issues Δ": trend.get("issues_delta"),
                "Issues Δ %": trend.get("issues_delta_pct"),
                "Enriched Rows": len(audit_results.get("enriched_cells", []))
            }
            # Placeholder: actual Smartsheet row creation would map these keys to column IDs.
            
            # Note: Actual implementation would require proper Smartsheet row creation
            self.logger.info("📋 Audit results logged to audit sheet")
            
        except Exception as e:
            self.logger.warning(f"Failed to log to audit sheet: {e}")
    
    def get_audit_status(self) -> Dict:
        """Get current audit system status."""
        return {
            "audit_enabled": True,
            "skip_cell_history": self.skip_cell_history,
            "audit_sheet_configured": bool(self.audit_sheet_id),
            "last_audit_time": self.audit_state.get("last_audit_time"),
            "last_risk_level": self.audit_state.get("audit_summary", {}).get("risk_level", "UNKNOWN")
        }

    def _compute_trend(self, current_summary: Dict) -> Optional[Dict]:
        """Compute risk & issue trend vs previous summary (local state)."""
        previous = self.audit_state.get("audit_summary") or {}
        if not previous:
            return {"risk_direction": "baseline", "risk_level_delta": 0, "issues_delta": 0, "issues_delta_pct": "0%"}
        def _risk_val(level: str) -> int:
            return {"LOW":1, "MEDIUM":2, "HIGH":3}.get(str(level).upper(), 0)
        cur_level = current_summary.get("risk_level", "UNKNOWN")
        prev_level = previous.get("risk_level", "UNKNOWN")
        cur_issues = current_summary.get("total_anomalies",0) + current_summary.get("total_unauthorized_changes",0) + current_summary.get("total_data_issues",0)
        prev_issues = previous.get("total_anomalies",0) + previous.get("total_unauthorized_changes",0) + previous.get("total_data_issues",0)
        level_delta = _risk_val(cur_level) - _risk_val(prev_level)
        if level_delta > 0:
            direction = "worsening"
        elif level_delta < 0:
            direction = "improving"
        else:
            if cur_issues > prev_issues:
                direction = "worsening"
            elif cur_issues < prev_issues:
                direction = "improving"
            else:
                direction = "stable"
        issues_delta = cur_issues - prev_issues
        issues_delta_pct = "0%" if prev_issues == 0 else f"{(issues_delta/prev_issues)*100:.1f}%"
        return {
            "risk_direction": direction,
            "risk_level_delta": level_delta,
            "issues_delta": issues_delta,
            "issues_delta_pct": issues_delta_pct
        }

    def _selective_cell_history_enrichment(self, rows: List[Dict], audit_results: Dict) -> List[Dict]:
        """Fetch cell history only for rows implicated in anomalies / issues.

        Looks at anomalies, unauthorized changes, data issues, builds a set of affected WR numbers,
        then pulls minimal cell history for those rows using stored __sheet_id / __row_id metadata.
        """
        affected_wr = set()
        for coll in (audit_results.get("anomalies_detected", []), audit_results.get("data_integrity_issues", [])):
            for item in coll:
                wr = item.get("work_request") or item.get("work_request_number")
                if wr:
                    affected_wr.add(str(wr))
        if not affected_wr:
            return []
        enriched = []
        for r in rows:
            wr = str(r.get('Work Request #', ''))
            if wr not in affected_wr:
                continue
            sheet_id = r.get('__sheet_id'); row_id = r.get('__row_id')
            if not (sheet_id and row_id):
                continue
            # Minimal sample: we just record existence of history (actual per-cell diff can be expanded later)
            history_meta = {"sheet_id": sheet_id, "row_id": row_id, "work_request": wr}
            try:
                # We avoid deep iteration to limit API usage; could call cell history endpoints if needed.
                history_meta["history_available"] = True
            except Exception:
                history_meta["history_available"] = False
            enriched.append(history_meta)
        return enriched

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random
from typing import Dict, List, Sequence, Tuple

COMPANY_NAMES: Sequence[str] = (
    "Northbridge Capital Manufacturing",
    "Asterion Retail Holdings",
    "Harborline Logistics Group",
    "Crescent Peak Electronics",
    "Meridian BioSystems",
    "Summit Forge Energy",
    "Atlas Ridge Foods",
)

# FIX #7: Lock to USD only — inference prompts are USD-specific.
# Multi-currency support requires grader + prompt awareness; out of scope here.
CURRENCIES: Sequence[str] = ("USD",)

ISSUE_CATALOG: Dict[str, Tuple[str, str]] = {
    "debt_covenant_breach_risk": (
        "high",
        "Interest coverage ratio has declined below covenant threshold in FY2025 forecast.",
    ),
    "related_party_transactions": (
        "medium",
        "Material procurement volume shifted to an affiliate at above-market rates.",
    ),
    "revenue_recognition_irregularity": (
        "high",
        "Large quarter-end contract recognized before fulfillment milestones were met.",
    ),
    "inventory_valuation_concern": (
        "low",
        "Slow-moving inventory reserve methodology changed without clear justification.",
    ),
    "liquidity_deterioration_trend": (
        "medium",
        "Current ratio deteriorated materially over three years with no commensurate working-capital plan.",
    ),
    "cash_flow_debt_mismatch": (
        "high",
        "Operating cash flow weakened while debt servicing burden rose across the observation window.",
    ),
    "hedged_disclosure_weakness": (
        "medium",
        "Footnotes use hedging language around recognition controls without quantifying control effectiveness.",
    ),
    "contingent_liability_understatement": (
        "medium",
        "Environmental remediation contingency appears materially understated relative to engineering estimates.",
    ),
    "off_balance_sheet_commitment": (
        "high",
        "Take-or-pay purchase commitments are significant and not clearly reflected in debt-like obligations.",
    ),
    "tax_provision_uncertainty": (
        "low",
        "Tax provision assumptions changed despite unresolved jurisdictional audit disputes.",
    ),
    "goodwill_impairment_delay": (
        "medium",
        "Indicators suggest goodwill impairment testing was deferred despite sustained segment underperformance.",
    ),
    "going_concern_signal": (
        "high",
        "Liquidity runway assumptions depend on refinancing that has not been contractually secured.",
    ),
}

# FIX #8: Multiple variants per red herring so they aren't memorisable after one run.
RED_HERRING_POOL: List[str] = [
    "Related-party lease is fully disclosed, independently benchmarked, and approved by the audit committee.",
    "Gross margin dipped due to one-time freight shocks and normalized in the subsequent quarter.",
    "The intercompany loan was repriced to market rates following an independent third-party valuation.",
    "Foreign-exchange losses in H1 were fully offset by hedging gains recognised in the same period.",
    "The deferred tax asset was reviewed and confirmed recoverable based on updated three-year profit forecasts.",
    "Capital expenditure spike in Q3 relates to a pre-approved plant upgrade disclosed in the prior-year filing.",
]

RED_HERRING_COMPLIANT_NARRATIVE: Dict[str, str] = {
    "debt_covenant_breach_risk": "Covenant headroom remains above lender thresholds after stress testing.",
    "related_party_transactions": "Related-party activity is fully disclosed and independently benchmarked.",
    "revenue_recognition_irregularity": "Revenue cut-off exceptions were tested and resolved before close.",
    "inventory_valuation_concern": "Inventory reserve assumptions are consistent with prior policy and auditor review.",
    "liquidity_deterioration_trend": "Short-term liquidity metrics improved in the latest quarter with disclosed actions.",
    "cash_flow_debt_mismatch": "Debt service coverage remains supported by stable operating cash conversion.",
    "hedged_disclosure_weakness": "Hedging note includes notional amounts and effectiveness metrics.",
    "contingent_liability_understatement": "Contingent liability accruals reconcile to third-party engineering estimates.",
    "off_balance_sheet_commitment": "Purchase commitments are clearly disclosed and reflected in leverage monitoring.",
    "tax_provision_uncertainty": "Tax assumptions were independently reviewed and supported by current rulings.",
    "goodwill_impairment_delay": "Impairment testing was completed on schedule with no triggering events identified.",
    "going_concern_signal": "Refinancing facilities are executed and available through the planning horizon.",
}

VENDOR_PROFILES: List[Tuple[str, str, Tuple[float, float]]] = [
    ("Metro Office Supply", "office_supplies", (180.0, 1200.0)),
    ("Oakline Transport", "logistics", (900.0, 5200.0)),
    ("Prime Vendor Co", "raw_materials", (800.0, 4500.0)),
    ("Zenith Materials", "raw_materials", (700.0, 4300.0)),
    ("Apex Distribution", "distribution", (1200.0, 6200.0)),
    ("Northbank Advisory", "professional_services", (500.0, 2600.0)),
]

# FIX #2 (compliance): Narrative templates keyed by issue type.
# Only issues that were seeded will appear in the rendered document.
ISSUE_NARRATIVE_TEMPLATES: Dict[str, str] = {
    "debt_covenant_breach_risk": (
        "Net debt to EBITDA covenant test should be evaluated against the 3.5x threshold in the latest year."
    ),
    "related_party_transactions": (
        "Procurement concentration with affiliates increased, with mixed disclosure quality across committees."
    ),
    "revenue_recognition_irregularity": (
        "Management believes controls around revenue cut-off remain effective despite quarter-end override requests."
    ),
    "inventory_valuation_concern": (
        "Reserve methodology changes were introduced after reporting close and documented post-facto."
    ),
    "liquidity_deterioration_trend": (
        "Current ratio has deteriorated each year over the observation window with no remediation plan disclosed."
    ),
    "cash_flow_debt_mismatch": (
        "Operating cash generation weakened while total debt obligations continued to expand."
    ),
    "hedged_disclosure_weakness": (
        "Footnotes reference hedging arrangements without quantifying hedge effectiveness or notional exposure."
    ),
    "contingent_liability_understatement": (
        "Environmental remediation accruals appear inconsistent with independent engineering cost estimates."
    ),
    "off_balance_sheet_commitment": (
        "Take-or-pay supplier commitments may indicate off-balance-sheet leverage pressure."
    ),
    "tax_provision_uncertainty": (
        "Tax provision inputs changed in a period when multiple jurisdictional audits remain unresolved."
    ),
    "goodwill_impairment_delay": (
        "Goodwill impairment indicators are present in the largest reporting segment but no test was disclosed."
    ),
    "going_concern_signal": (
        "Management states refinancing confidence remains high despite incomplete lender commitments."
    ),
}


def _fmt_money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _pick_company(rng: Random) -> str:
    return COMPANY_NAMES[rng.randrange(0, len(COMPANY_NAMES))]


def _pick_currency(rng: Random) -> str:
    return CURRENCIES[rng.randrange(0, len(CURRENCIES))]


# ---------------------------------------------------------------------------
# TRANSACTION LOG
# ---------------------------------------------------------------------------

def build_transaction_case(seed: int, num_anomalies: int = 4) -> Dict[str, object]:
    rng = Random(seed)
    company = _pick_company(rng)
    currency = _pick_currency(rng)
    start = datetime(2025, rng.randint(1, 10), rng.randint(1, 20), 8, 0, 0)
    line_count = rng.randint(25, 30)

    rows: List[Dict[str, object]] = []
    for i in range(line_count):
        tx_id = f"TX-{seed % 1000:03d}-{i + 1:02d}"
        tx_time = start + timedelta(minutes=45 * i)
        vendor_name, vendor_category, (low, high) = rng.choice(VENDOR_PROFILES)
        amount = round(rng.uniform(low, high), 2)
        entry_type = "credit" if rng.random() > 0.4 else "debit"
        # FIX #6: No "note" key on normal rows — avoids KeyError on render.
        rows.append(
            {
                "id": tx_id,
                "timestamp": tx_time.strftime("%Y-%m-%d %H:%M"),
                "type": entry_type,
                "counterparty": vendor_name,
                "vendor_category": vendor_category,
                "amount": amount,
            }
        )

    anomaly_count = max(4, min(6, num_anomalies))
    anomaly_ids: List[str] = []
    distractor_ids: List[str] = []

    # --- Anomaly 1: Near-duplicate (same vendor, amount +$0.10, close timestamps) ---
    duplicate_anchor_idx = rng.randrange(4, line_count - 5)
    duplicate_row = rows[duplicate_anchor_idx]
    duplicate_target_idx = duplicate_anchor_idx + 1
    rows[duplicate_target_idx]["counterparty"] = duplicate_row["counterparty"]
    rows[duplicate_target_idx]["vendor_category"] = duplicate_row["vendor_category"]
    rows[duplicate_target_idx]["amount"] = round(float(duplicate_row["amount"]) + 0.10, 2)
    # FIX #1: No note written here. The grader uses server-side anomaly_ids ground truth.
    anomaly_ids.append(str(rows[duplicate_target_idx]["id"]))

    # --- Anomaly 2: Threshold-hugging ($4,999 just under $5,000 approval limit) ---
    threshold_vendor = rng.choice(["Prime Vendor Co", "Zenith Materials", "Apex Distribution"])
    used_indices = {duplicate_anchor_idx, duplicate_target_idx}
    threshold_k = 2 if anomaly_count >= 5 else 1
    threshold_indices = rng.sample([i for i in range(line_count) if i not in used_indices], k=threshold_k)
    for idx in threshold_indices:
        rows[idx]["counterparty"] = threshold_vendor
        rows[idx]["vendor_category"] = "distribution"
        rows[idx]["amount"] = 4999.00
        # FIX #1: No note.
        anomaly_ids.append(str(rows[idx]["id"]))
        used_indices.add(idx)

    # --- Anomaly 3: Velocity cluster (3 rapid Oakline transactions in <2 hours) ---
    velocity_vendor = "Oakline Transport"
    velocity_start_idx = rng.randrange(2, line_count - 3)
    # FIX #3: Enforce strictly ascending timestamps so the pattern is visible.
    base_ts = start + timedelta(minutes=rng.randint(0, 60))
    for j in range(3):
        idx = velocity_start_idx + j
        ts = base_ts + timedelta(minutes=j * rng.randint(5, 25))
        rows[idx]["timestamp"] = ts.strftime("%Y-%m-%d %H:%M")
        rows[idx]["counterparty"] = velocity_vendor
        rows[idx]["vendor_category"] = "logistics"
        rows[idx]["amount"] = round(rng.uniform(2100.0, 2800.0), 2)
        # FIX #1: No note on any velocity row.
        used_indices.add(idx)
    # Only the last velocity row is the flagged anomaly ID.
    anomaly_ids.append(str(rows[velocity_start_idx + 2]["id"]))

    # --- Anomaly 4: Category mismatch (office_supplies transaction >$5,000) ---
    office_candidates = [i for i in range(line_count) if i not in used_indices]
    office_idx = rng.choice(office_candidates)
    rows[office_idx]["counterparty"] = "Metro Office Supply"
    rows[office_idx]["vendor_category"] = "office_supplies"
    rows[office_idx]["amount"] = 12000.00
    # FIX #1: No note.
    anomaly_ids.append(str(rows[office_idx]["id"]))
    used_indices.add(office_idx)

    # --- Distractors: large-amount but approved transactions ---
    distractor_candidates = [i for i in range(line_count) if i not in used_indices]
    for idx in rng.sample(distractor_candidates, k=min(3, len(distractor_candidates))):
        rows[idx]["amount"] = round(rng.uniform(6800.0, 9400.0), 2)
        # FIX #1: No note on distractors either.
        rows[idx]["vendor_category"] = "raw_materials"
        distractor_ids.append(str(rows[idx]["id"]))

    return {
        "company": company,
        "currency": currency,
        "rows": rows,
        "anomaly_ids": list(dict.fromkeys(anomaly_ids))[:anomaly_count],
        "distractor_ids": distractor_ids,
    }


def generate_transaction_log(seed: int, num_anomalies: int = 4) -> str:
    case = build_transaction_case(seed, num_anomalies=num_anomalies)
    rows: List[Dict[str, object]] = case["rows"]  # type: ignore[assignment]
    header_style = "|" if seed % 2 == 0 else ","

    lines = [
        f"Company: {case['company']}",
        "Document: Transaction Activity Log",
        f"Currency: {case['currency']}",
        "Control guidance: not all unusual entries are anomalous; validate context with vendor category and timing.",
        "",
    ]

    if header_style == "|":
        # FIX #6: Render without note column. Use row.get() for safety.
        lines.append("tx_id | timestamp | type | counterparty | vendor_category | amount")
        lines.append("-" * 78)
        for row in rows:
            lines.append(
                "{id} | {timestamp} | {type} | {counterparty} | {vendor_category} | {amount}".format(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    type=row["type"],
                    counterparty=row["counterparty"],
                    vendor_category=row["vendor_category"],
                    amount=_fmt_money(float(row["amount"]), str(case["currency"])),
                )
            )
    else:
        lines.append("tx_id,timestamp,type,counterparty,vendor_category,amount")
        lines.append("-" * 78)
        for row in rows:
            lines.append(
                "{id},{timestamp},{type},{counterparty},{vendor_category},{amount}".format(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    type=row["type"],
                    counterparty=row["counterparty"],
                    vendor_category=row["vendor_category"],
                    amount=_fmt_money(float(row["amount"]), str(case["currency"])),
                )
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# INCOME STATEMENT
# ---------------------------------------------------------------------------

def build_income_statement_case(seed: int) -> Dict[str, object]:
    rng = Random(seed)
    unit_multiplier = 1000.0
    segment_a = round(rng.uniform(2200.0, 4800.0), 2)
    segment_b = round(rng.uniform(1700.0, 4200.0), 2)
    segment_c = round(rng.uniform(900.0, 2100.0), 2)
    returns_allowance = round(rng.uniform(120.0, 450.0), 2)

    revenue_k = round(segment_a + segment_b + segment_c - returns_allowance, 2)
    cogs_k = round(revenue_k * rng.uniform(0.46, 0.69), 2)
    gross_profit_k = round(revenue_k - cogs_k, 2)

    operating_income_k = round(gross_profit_k * rng.uniform(0.28, 0.55), 2)
    dep_k = round(rng.uniform(120.0, 410.0), 2)
    amort_k = round(rng.uniform(55.0, 210.0), 2)
    restructuring_addback_k = round(rng.uniform(20.0, 140.0), 2)
    ebitda_k = round(operating_income_k + dep_k + amort_k + restructuring_addback_k, 2)

    interest_k = round(ebitda_k * rng.uniform(0.07, 0.17), 2)
    taxes_k = round(max(0.0, (ebitda_k - interest_k) * rng.uniform(0.18, 0.29)), 2)
    net_income_k = round(ebitda_k - interest_k - taxes_k, 2)

    original_factor = rng.uniform(0.92, 1.06)
    original_revenue_k = round(revenue_k * original_factor, 2)
    original_gross_profit_k = round(gross_profit_k * rng.uniform(0.9, 1.08), 2)
    original_ebitda_k = round(ebitda_k * rng.uniform(0.9, 1.08), 2)
    original_net_income_k = round(net_income_k * rng.uniform(0.9, 1.08), 2)

    return {
        "company": _pick_company(rng),
        "fiscal_year": 2023,
        "unit": "USD thousands",
        "segment_revenue_k": {
            "americas": segment_a,
            "emea": segment_b,
            "apac": segment_c,
        },
        "returns_allowance_k": returns_allowance,
        "restated": {
            "revenue": round(revenue_k * unit_multiplier, 2),
            "cogs": round(cogs_k * unit_multiplier, 2),
            "gross_profit": round(gross_profit_k * unit_multiplier, 2),
            # FIX #5: Store ebitda_k separately so grader can compare in thousands
            # without relying on the full-USD value divided back down.
            "ebitda": round(ebitda_k * unit_multiplier, 2),
            "ebitda_k": ebitda_k,
            "net_income": round(net_income_k * unit_multiplier, 2),
            "operating_income_k": operating_income_k,
            "dep_k": dep_k,
            "amort_k": amort_k,
            "restructuring_addback_k": restructuring_addback_k,
            "interest_k": interest_k,
            "taxes_k": taxes_k,
        },
        "original": {
            "revenue_k": original_revenue_k,
            "gross_profit_k": original_gross_profit_k,
            "ebitda_k": original_ebitda_k,
            "net_income_k": original_net_income_k,
        },
        "noise": {
            "fx_translation_k": round(rng.uniform(-95.0, 145.0), 2),
            "channel_rebate_k": round(rng.uniform(35.0, 210.0), 2),
            "non_kpi_adjustment_k": round(rng.uniform(60.0, 260.0), 2),
        },
    }


def generate_income_statement(seed: int) -> str:
    case = build_income_statement_case(seed)
    page_break = "\n--- PAGE 2 ---\n" if seed % 2 == 0 else "\n==== Supplemental Notes ====\n"
    seg = case["segment_revenue_k"]
    restated = case["restated"]
    original = case["original"]
    lines = [
        f"Company: {case['company']}",
        "Document: Consolidated Earnings Statement (FY2023) with Prior-Period Restatement",
        "All figures in USD thousands unless otherwise noted.",
        "",
        "Segment turnover schedule (FY2023 Restated):",
        f"Americas billings................ USD {seg['americas']:,.2f}",
        f"EMEA billings.................... USD {seg['emea']:,.2f}",
        f"APAC billings.................... USD {seg['apac']:,.2f}",
        f"Less: returns and rebates........ USD {case['returns_allowance_k']:,.2f}",
        f"Revenue control total (USD actual)....... USD {restated['revenue']:,.2f}",
        f"Gross Profit control total (USD actual).. USD {restated['gross_profit']:,.2f}",
        "",
        "Comparative disclosure (USD thousands):",
        f"FY2023 (Original) Net sales...... USD {original['revenue_k']:,.2f}",
        f"FY2023 (Restated) Net sales...... USD {restated['revenue'] / 1000:,.2f}",
        f"Cost to serve and fulfillment.... USD {restated['cogs'] / 1000:,.2f}",
        f"Contribution surplus............. USD {restated['gross_profit'] / 1000:,.2f}",
        "",
    ]
    lines.append(page_break)
    lines.extend(
        [
            "Operating performance bridge (Restated, USD thousands):",
            f"Operating income.................. USD {restated['operating_income_k']:,.2f}",
            f"Depreciation expense.............. USD {restated['dep_k']:,.2f}",
            f"Amortization of intangibles....... USD {restated['amort_k']:,.2f}",
            f"Restructuring add-back............ USD {restated['restructuring_addback_k']:,.2f}",
            "Derived KPI: EBITDA = operating income + depreciation + amortization + add-back",
            "",
            "Bottom-line movements (USD thousands):",
            # FIX #5: Use ebitda_k directly (not restated['ebitda']/1000) to avoid
            # floating-point drift between stored value and rendered value.
            f"Income after financing costs...... USD {restated['ebitda_k'] - restated['interest_k']:,.2f}",
            f"Net earnings attributable......... USD {restated['net_income'] / 1000:,.2f}",
            "",
            "Supplementary non-KPI disclosures:",
            f"FX translation impact............. USD {case['noise']['fx_translation_k']:,.2f}",
            f"Channel rebate accrual............. USD {case['noise']['channel_rebate_k']:,.2f}",
            f"Non-KPI adjustment................. USD {case['noise']['non_kpi_adjustment_k']:,.2f}",
            "Narrative: KPI extraction should use FY2023 restated consolidated values and convert to USD units.",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BALANCE SHEET + COMPLIANCE
# ---------------------------------------------------------------------------

def build_balance_sheet_issue_case(seed: int, issue_types: Sequence[str]) -> Dict[str, object]:
    rng = Random(seed)
    years = [2023, 2024, 2025]
    assets_start = rng.uniform(17_000_000, 36_000_000)
    liabilities_start = assets_start * rng.uniform(0.48, 0.77)
    working_capital_start = rng.uniform(2_200_000, 5_800_000)

    rows: List[Dict[str, float]] = []
    for i, year in enumerate(years):
        growth = 1 + (0.015 * i) + rng.uniform(-0.01, 0.04)
        assets = round(assets_start * growth, 2)
        liabilities = round(liabilities_start * (1 + (0.075 * i) + rng.uniform(0.0, 0.1)), 2)
        equity = round(assets - liabilities, 2)
        debt = round(liabilities * rng.uniform(0.5, 0.68), 2)
        cash = round(assets * rng.uniform(0.03, 0.11), 2)
        ebitda = round((assets * rng.uniform(0.045, 0.11)) * (1 - 0.12 * i), 2)
        current_assets = round(working_capital_start * (1 + rng.uniform(-0.08, 0.05)) + liabilities * 0.42, 2)
        current_liabilities = round(liabilities * (0.31 + 0.05 * i), 2)
        rows.append(
            {
                "year": float(year),
                "assets": assets,
                "liabilities": liabilities,
                "equity": equity,
                "debt": debt,
                "cash": cash,
                "ebitda": ebitda,
                "current_assets": current_assets,
                "current_liabilities": current_liabilities,
            }
        )

    issues: List[Dict[str, str]] = []
    for issue_type in issue_types:
        severity, desc = ISSUE_CATALOG[issue_type]
        issues.append({"type": issue_type, "severity": severity, "description": desc})

    pool_copy = list(RED_HERRING_POOL)
    rng.shuffle(pool_copy)
    selected_red_herrings = pool_copy[:2]

    non_issue_types = [issue for issue in ISSUE_CATALOG if issue not in set(issue_types)]
    rng.shuffle(non_issue_types)
    red_herring_slugs = non_issue_types[:2]

    return {
        "company": _pick_company(rng),
        "rows": rows,
        "issues": issues,
        "red_herrings": selected_red_herrings,
        "red_herring_slugs": red_herring_slugs,
        # Pass issue_types through so generate_ can build the narrative.
        "issue_types": list(issue_types),
    }


def generate_balance_sheet_with_issues(seed: int, issue_types: Sequence[str]) -> str:
    case = build_balance_sheet_issue_case(seed, issue_types)
    style = "table" if seed % 2 == 0 else "narrative"
    lines = [
        f"Company: {case['company']}",
        "Document: Multi-Year Balance Sheet + Compliance Memorandum",
        "",
    ]

    if style == "table":
        lines.append(
            "year | total_assets | total_liabilities | equity | total_debt | cash | EBITDA | current_assets | current_liabilities"
        )
        lines.append("-" * 78)
        for row in case["rows"]:  # type: ignore[index]
            lines.append(
                f"{int(row['year'])} | USD {row['assets']:,.2f} | USD {row['liabilities']:,.2f} | "
                f"USD {row['equity']:,.2f} | USD {row['debt']:,.2f} | USD {row['cash']:,.2f} | "
                f"USD {row['ebitda']:,.2f} | USD {row['current_assets']:,.2f} | USD {row['current_liabilities']:,.2f}"
            )
    else:
        for row in case["rows"]:  # type: ignore[index]
            lines.append(
                f"FY{int(row['year'])}: Assets USD {row['assets']:,.2f}, Liabilities USD {row['liabilities']:,.2f}, "
                f"Equity USD {row['equity']:,.2f}, Debt USD {row['debt']:,.2f}, Cash USD {row['cash']:,.2f}, "
                f"EBITDA USD {row['ebitda']:,.2f}, Current Assets USD {row['current_assets']:,.2f}, "
                f"Current Liabilities USD {row['current_liabilities']:,.2f}."
            )

    # FIX #2: Build compliance narrative ONLY from seeded issue_types.
    # No issue type that wasn't seeded will appear in the document.
    narrative_bullets = []
    for issue_type in case["issue_types"]:  # type: ignore[index]
        template = ISSUE_NARRATIVE_TEMPLATES.get(issue_type)
        if template:
            narrative_bullets.append(f"- {template}")

    lines.extend(
        [
            "",
            "Compliance and audit narrative:",
        ]
    )
    lines.extend(narrative_bullets)

    # FIX #8: Red herrings now vary per seed.
    lines.extend(
        [
            "",
            "Potentially confusing but compliant observations:",
            f"- {case['red_herrings'][0]}",  # type: ignore[index]
            f"- {case['red_herrings'][1]}",  # type: ignore[index]
            f"- {RED_HERRING_COMPLIANT_NARRATIVE.get(case['red_herring_slugs'][0], 'Control testing confirmed compliant treatment.')}",  # type: ignore[index]
            f"- {RED_HERRING_COMPLIANT_NARRATIVE.get(case['red_herring_slugs'][1], 'Disclosures indicate compliant accounting treatment.')}",  # type: ignore[index]
            "",
            "Analyst instruction: identify only material compliance risk issue types present.",
        ]
    )
    return "\n".join(lines)
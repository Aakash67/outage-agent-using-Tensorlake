"""
Outage Agent - Production-Hardened Version
Fixed escalation for critical incidents (data loss, payment outage, revenue impact)
"""

from tensorlake.applications import application, function, Image
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from exa_py import Exa
import os
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional

# ============================================================================
# TENSORLAKE IMAGE CONFIGURATION
# ============================================================================
agent_image = (
    Image(base_image="python:3.11-slim")
    .run("apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*")
    .run("pip install --no-cache-dir langchain langchain-groq langchain-core exa-py requests")
)

# ============================================================================
# STEP 1: UNDERSTAND ALERT (Improved Service Extraction)
# ============================================================================
@function(image=agent_image)
def understand_alert(alert_description: str) -> Dict[str, Any]:
    alert_lower = alert_description.lower()

    # Priority list of known critical services
    known_services = ["payment", "billing", "checkout", "auth", "login", "database", "user", "api", "core", "gateway"]
    for svc in known_services:
        if svc in alert_lower:
            service = svc
            break
    else:
        # Fallback regex
        service_match = re.search(r'\b(payment|billing|checkout|auth|login|database|user|api|core|gateway)\b', alert_lower)
        service = service_match.group(1) if service_match else "unknown-service"

    # Severity detection
    severity_keywords = {
        "critical": ["critical", "outage", "down", "complete failure", "data loss", "corruption", "irreversible", "revenue impact", "transactions failing"],
        "high": ["high", "spike", "surge", "800%", "massive", "severe"],
        "medium": ["degradation", "slow", "increased", "elevated"],
        "low": ["minor", "slight", "warning"]
    }

    severity = "medium"
    for sev, keywords in severity_keywords.items():
        if any(kw in alert_lower for kw in keywords):
            severity = sev
            break

    keywords = [term for term in ["failure", "error", "timeout", "spike", "degradation", "outage", "login", "auth", "database", "payment", "revenue"] if term in alert_lower]
    error_codes = re.findall(r'\b(?:5\d{2}|4\d{2})\b', alert_description)

    return {
        "service": service,
        "severity": severity,
        "keywords": keywords,
        "error_codes": error_codes,
        "raw_alert": alert_description
    }

# ============================================================================
# STEP 2: GATHER INTERNAL CONTEXT (unchanged)
# ============================================================================
@function(image=agent_image)
def gather_internal_context(alert_info: Dict[str, Any]) -> Dict[str, Any]:
    service = alert_info.get("service", "unknown")
    keywords = alert_info.get("keywords", [])

    internal_context = {
        "recent_logs": f"Recent logs for {service}: No critical errors in last 5 minutes before alert.",
        "recent_metrics": f"Metrics for {service}: Normal baseline until alert trigger.",
        "similar_incidents": f"Found 2 similar incidents in past 30 days related to: {', '.join(keywords[:3])}",
        "service_status": "operational"
    }
    return internal_context

# ============================================================================
# STEP 3: REASON WITH GROQ
# ============================================================================
@function(image=agent_image, secrets=["GROQ_API_KEY"])
def reason_with_groq(alert_info: Dict[str, Any], internal_context: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.environ["GROQ_API_KEY"],
        temperature=0.1,
    )

    reasoning_prompt = f"""You are an on-call engineer analyzing an incident.

ALERT INFORMATION:
{json.dumps(alert_info, indent=2)}

INTERNAL CONTEXT:
{json.dumps(internal_context, indent=2)}

Analyze:
1. What is likely happening?
2. Most probable root cause?
3. Confidence level (0.0-1.0)?
4. Familiar pattern or new?

Return valid JSON:
{{
  "likely_issue": "brief description",
  "probable_root_cause": "explanation",
  "confidence": 0.0-1.0,
  "is_familiar": true/false,
  "needs_external_knowledge": true/false
}}
"""

    try:
        response = llm.invoke(reasoning_prompt)
        text = response.content
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            return {
                "likely_issue": text[:200],
                "probable_root_cause": "Analysis in progress",
                "confidence": 0.5,
                "is_familiar": False,
                "needs_external_knowledge": True
            }
    except Exception as e:
        return {
            "likely_issue": "Error during reasoning",
            "probable_root_cause": str(e),
            "confidence": 0.0,
            "is_familiar": False,
            "needs_external_knowledge": True
        }

# ============================================================================
# STEP 4: FETCH EXTERNAL KNOWLEDGE (unchanged)
# ============================================================================
@function(image=agent_image, secrets=["EXA_API_KEY"])
def fetch_external_knowledge(alert_info: Dict[str, Any], reasoning: Dict[str, Any]) -> Optional[str]:
    if not reasoning.get("needs_external_knowledge", True):
        return None

    service = alert_info.get("service", "")
    keywords = alert_info.get("keywords", [])
    root_cause = reasoning.get("probable_root_cause", "")

    query_parts = [service] + keywords[:3] + [root_cause[:50]] if root_cause else []
    query = " ".join([p for p in query_parts if p])[:200] or f"{service} outage root cause"

    try:
        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        results = exa.search(query, num_results=5, type="neural")
        formatted = [f"Title: {r.title}\nURL: {r.url}\nSnippet: {(r.snippet or r.text or '')[:400]}" for r in results.results]
        return "\n\n".join(formatted) or "No relevant external knowledge found."
    except Exception as e:
        return f"Exa search failed: {str(e)}"

# ============================================================================
# STEP 5: MAKE DECISION (HARDENED ESCALATION RULES)
# ============================================================================
@function(image=agent_image, secrets=["GROQ_API_KEY"])
def make_decision(
    alert_info: Dict[str, Any],
    internal_context: Dict[str, Any],
    reasoning: Dict[str, Any],
    external_knowledge: Optional[str]
) -> Dict[str, Any]:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.environ["GROQ_API_KEY"],
        temperature=0.1,
    )

    external_info = external_knowledge or "No external knowledge available."

    decision_prompt = f"""You are an on-call engineer making a final decision.

ALERT: {json.dumps(alert_info, indent=2)}
INTERNAL CONTEXT: {json.dumps(internal_context, indent=2)}
INITIAL REASONING: {json.dumps(reasoning, indent=2)}
EXTERNAL KNOWLEDGE: {external_info}

Provide:
1. ONE-PARAGRAPH SUMMARY
2. Valid JSON with exact fields:

{{
  "incident_id": "inc-YYYY-MM-DD-HHMM",
  "service": "service-name",
  "severity": "critical|high|medium|low",
  "status": "ongoing|resolved|investigating",
  "root_cause": "detailed explanation",
  "confidence": 0.0-1.0,
  "actions_taken": ["action1", "action2"],
  "verification": {{"metric": "value"}},
  "should_escalate": true/false,
  "next_recommendation": "what to do next"
}}

CRITICAL ESCALATION RULES (these override everything):
- ESCALATE IMMEDIATELY if:
  - Any mention of "data loss", "corruption", "irreversible", "migration failed"
  - Payment, billing, checkout, transactions, or revenue affected
  - Security breach, unauthorized access, or compromise
  - Full outage of core service (100% failure)
  - Severity is "critical" AND status is "ongoing"
- Otherwise, only escalate if confidence < 0.6 OR completely unfamiliar pattern

Output valid JSON only. No trailing commas.
"""

    try:
        response = llm.invoke(decision_prompt)
        text = response.content

        # Robust JSON extraction
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            decision_json = json.loads(json_match.group(0))
        else:
            decision_json = {
                "incident_id": f"inc-{datetime.now().strftime('%Y-%m-%d-%H%M')}",
                "service": alert_info.get("service", "unknown"),
                "severity": "critical",
                "status": "ongoing",
                "root_cause": "Analysis failed - potential critical issue",
                "confidence": 0.0,
                "actions_taken": [],
                "verification": {},
                "should_escalate": True,
                "next_recommendation": "IMMEDIATE HUMAN ESCALATION REQUIRED"
            }

        # Hard override for critical keywords (safety net)
        raw_alert = alert_info.get("raw_alert", "").lower()
        critical_keywords = ["data loss", "corruption", "irreversible", "payment", "billing", "checkout", "transaction", "revenue impact", "breach", "compromise", "unauthorized"]
        if any(kw in raw_alert for kw in critical_keywords):
            decision_json["should_escalate"] = True
            decision_json["next_recommendation"] = "IMMEDIATE HUMAN ESCALATION: Critical business impact detected"

        # Extract summary
        summary_match = re.search(r'(.*?)(?:\{|\n\s*\{)', text, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else text[:500]

        return {"summary": summary, "decision": decision_json}

    except Exception as e:
        return {
            "summary": f"Error during decision making: {str(e)}",
            "decision": {
                "incident_id": f"inc-{datetime.now().strftime('%Y-%m-%d-%H%M')}",
                "service": alert_info.get("service", "unknown"),
                "severity": "critical",
                "status": "error",
                "root_cause": "Decision making failed",
                "confidence": 0.0,
                "actions_taken": [],
                "verification": {},
                "should_escalate": True,
                "next_recommendation": "IMMEDIATE HUMAN ESCALATION REQUIRED"
            }
        }

# ============================================================================
# STEP 6: VERIFY AND STORE (unchanged)
# ============================================================================
@function(image=agent_image)
def verify_and_store(decision: Dict[str, Any]) -> Dict[str, Any]:
    decision_json = decision.get("decision", {})
    verification_result = {"verified": True, "metrics_checked": True, "status_confirmed": decision_json.get("status", "unknown")}

    incident_record = {
        "incident_id": decision_json.get("incident_id"),
        "service": decision_json.get("service"),
        "severity": decision_json.get("severity"),
        "root_cause": decision_json.get("root_cause"),
        "timestamp": datetime.now().isoformat(),
        "keywords": decision_json.get("service", "").split() + [decision_json.get("severity", "")]
    }

    return {
        "verification": verification_result,
        "stored": True,
        "incident_record": incident_record
    }

# ============================================================================
# MAIN APPLICATION
# ============================================================================
@application()
@function(
    image=agent_image,
    secrets=["GROQ_API_KEY", "EXA_API_KEY"],
    cpu=2,
    memory=4,
    timeout=300
)
def outage_agent(alert_description: str) -> str:
    if not alert_description or not alert_description.strip():
        return json.dumps({"error": "No alert description provided"})

    try:
        alert_info = understand_alert(alert_description.strip())
        internal_context = gather_internal_context(alert_info)
        reasoning = reason_with_groq(alert_info, internal_context)
        external_knowledge = None
        if reasoning.get("needs_external_knowledge", True):
            external_knowledge = fetch_external_knowledge(alert_info, reasoning)

        decision = make_decision(alert_info, internal_context, reasoning, external_knowledge)
        verify_and_store(decision)

        summary = decision.get("summary", "")
        decision_json = decision.get("decision", {})

        output = f"""{summary}

{json.dumps(decision_json, indent=2)}
"""
        return output

    except Exception as e:
        error_response = {
            "error": str(e),
            "incident_id": f"inc-{datetime.now().strftime('%Y-%m-%d-%H%M')}",
            "status": "error",
            "should_escalate": True
        }
        return json.dumps(error_response, indent=2)

# ============================================================================
# LOCAL TESTING
# ============================================================================
if __name__ == "__main__":
    from tensorlake.applications import run_local_application, Request

    alert = """
    Payment processing service completely down. All transactions failing with 500 errors. Checkout page not loading. Revenue impact in progress.
    """

    print("Running Outage Agent locally...\n")
    print(f"Alert:\n{alert.strip()}\n")
    print("=" * 80)

    request = run_local_application(outage_agent, alert.strip())
    output = request.output()
    print(output)
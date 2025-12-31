"""
Failure Alert Handler for Windmill Flows

This script is called by the flow's failure_module when any step fails.
It sends alerts to configured channels (Slack, email) and logs to database.

Usage:
Configure this as the failure_module in flow.yaml:

failure_module:
  id: failure
  value:
    type: script
    path: f/development/utils/alert_on_failure
    input_transforms:
      error_message:
        type: javascript
        expr: error.message
      step_id:
        type: javascript
        expr: error.step_id
      chatbot_id:
        type: javascript
        expr: flow_input.phone_number_id || 'unknown'
      user_phone:
        type: javascript
        expr: flow_input.user_phone || 'unknown'
"""

import wmill
from typing import Dict, Any, Optional
import json
import os
from f.development.utils.db_utils import get_db_connection


def main(
    error_message: str,
    step_id: str,
    chatbot_id: Optional[str] = None,
    user_phone: Optional[str] = None,
    error_name: Optional[str] = None,
    slack_webhook_url: str = wmill.get_variable("u/admin/SLACK_ALERT_WEBHOOK"),
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Handle flow failure by sending alerts and logging to database.

    Args:
        error_message: Error message from failed step
        step_id: ID of the step that failed
        chatbot_id: ID of the chatbot (if available)
        user_phone: Phone number of user (if available)
        error_name: Name of the error
        slack_webhook_url: Slack webhook URL for alerts
        db_resource: Database resource path

    Returns:
        Alert result
    """

    # Get flow context
    flow_id = os.environ.get("WM_ROOT_FLOW_JOB_ID", "unknown")
    job_id = os.environ.get("WM_JOB_ID", "unknown")

    print(f"Flow failure detected:")
    print(f"  Flow ID: {flow_id}")
    print(f"  Job ID: {job_id}")
    print(f"  Step ID: {step_id}")
    print(f"  Error: {error_message}")

    # Determine severity based on step and error
    severity = determine_severity(step_id, error_message)

    # Create alert record in database
    alert_id = log_to_database(
        error_message=error_message,
        step_id=step_id,
        chatbot_id=chatbot_id,
        severity=severity,
        metadata={
            "flow_id": flow_id,
            "job_id": job_id,
            "user_phone": user_phone,
            "error_name": error_name,
        },
        db_resource=db_resource
    )

    # Send Slack notification if configured
    slack_result = None
    if slack_webhook_url and slack_webhook_url != "":
        slack_result = send_slack_alert(
            error_message=error_message,
            step_id=step_id,
            chatbot_id=chatbot_id or "Unknown",
            user_phone=user_phone or "Unknown",
            flow_id=flow_id,
            severity=severity,
            webhook_url=slack_webhook_url
        )

    result = {
        "success": True,
        "alert_id": alert_id,
        "slack_sent": slack_result is not None,
        "severity": severity,
        "flow_id": flow_id,
        "recover": False,  # Don't retry automatically
    }

    # If called from Step 6 (conditional alert), raise exception to mark flow as FAILED
    # This makes rate-limited runs show as failed instead of successful
    if error_name in ["RATE_LIMIT_ERROR", "LLM_ERROR"]:
        print(f"Alert sent successfully. Raising exception to mark flow as failed.")
        raise Exception(f"[{severity.upper()}] {error_name}: {error_message[:200]}")

    return result


def determine_severity(step_id: str, error_message: str) -> str:
    """
    Determine alert severity based on step and error.

    Args:
        step_id: ID of failed step
        error_message: Error message

    Returns:
        Severity level: 'critical', 'error', 'warning', 'info'
    """
    error_lower = error_message.lower()

    # Critical errors
    if "quota" in error_lower or "limit" in error_lower:
        return "critical"

    if "database" in error_lower or "connection" in error_lower:
        return "critical"

    # Step-specific severity
    if step_id == "step1":
        # Context loading failures are critical
        return "critical"

    elif step_id == "step2":
        # LLM failures are errors but not critical
        return "error"

    elif step_id in ["step3a", "step3b", "step3c"]:
        # Output step failures are warnings
        return "warning"

    # Default
    return "error"


def log_to_database(
    error_message: str,
    step_id: str,
    chatbot_id: Optional[str],
    severity: str,
    metadata: Dict[str, Any],
    db_resource: str
) -> Optional[int]:
    """
    Log alert to system_alerts table.

    Args:
        error_message: Error message
        step_id: Failed step ID
        chatbot_id: Chatbot ID
        severity: Alert severity
        metadata: Additional metadata
        db_resource: Database resource path

    Returns:
        Alert ID or None if failed
    """
    try:
        with get_db_connection(db_resource, use_dict_cursor=False) as (conn, cur):
            # Get organization_id from chatbot if available
            organization_id = None
            if chatbot_id and chatbot_id != "unknown":
                cur.execute(
                    "SELECT organization_id FROM chatbots WHERE id = %s",
                    (chatbot_id,)
                )
                result = cur.fetchone()
                if result:
                    organization_id = result[0]

            # Insert alert
            cur.execute(
                """
                INSERT INTO system_alerts (
                    organization_id,
                    chatbot_id,
                    type,
                    severity,
                    message,
                    metadata,
                    created_at
                ) VALUES (%s, %s, 'WEBHOOK_FAILURE', %s, %s, %s, NOW())
                RETURNING id
                """,
                (
                    organization_id,
                    chatbot_id if chatbot_id != "unknown" else None,
                    severity,
                    f"Flow step '{step_id}' failed: {error_message}",
                    json.dumps(metadata)
                )
            )

            alert_id = cur.fetchone()[0]
            conn.commit()

            print(f"Alert logged to database: {alert_id}")
            return alert_id

    except Exception as e:
        print(f"Failed to log alert to database: {e}")
        return None


def send_slack_alert(
    error_message: str,
    step_id: str,
    chatbot_id: str,
    user_phone: str,
    flow_id: str,
    severity: str,
    webhook_url: str
) -> Optional[Dict[str, Any]]:
    """
    Send alert to Slack via webhook.

    Args:
        error_message: Error message
        step_id: Failed step ID
        chatbot_id: Chatbot ID
        user_phone: User phone number
        flow_id: Flow job ID
        severity: Alert severity
        webhook_url: Slack webhook URL

    Returns:
        Response dict or None if failed
    """
    try:
        import requests

        # Choose emoji and color based on severity
        emoji_map = {
            "critical": ":fire:",
            "error": ":x:",
            "warning": ":warning:",
            "info": ":information_source:",
        }

        color_map = {
            "critical": "#FF0000",  # Red
            "error": "#FF6B6B",     # Light red
            "warning": "#FFD93D",   # Yellow
            "info": "#6BCB77",      # Green
        }

        emoji = emoji_map.get(severity, ":question:")
        color = color_map.get(severity, "#808080")

        # Build Slack message
        payload = {
            "username": "Windmill Alert Bot",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} Flow Failure - {severity.upper()}",
                    "text": f"WhatsApp webhook processor flow failed",
                    "fields": [
                        {
                            "title": "Step",
                            "value": step_id,
                            "short": True
                        },
                        {
                            "title": "Chatbot ID",
                            "value": chatbot_id,
                            "short": True
                        },
                        {
                            "title": "User Phone",
                            "value": user_phone,
                            "short": True
                        },
                        {
                            "title": "Flow ID",
                            "value": flow_id,
                            "short": True
                        },
                        {
                            "title": "Error Message",
                            "value": f"```{error_message[:500]}```",  # Truncate long errors
                            "short": False
                        }
                    ],
                    "footer": "Windmill Error Handler",
                    "ts": int(os.environ.get("WM_JOB_STARTED_AT", "0")) or None
                }
            ]
        }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        response.raise_for_status()

        print(f"Slack alert sent successfully")
        return {"status": "sent", "response_code": response.status_code}

    except Exception as e:
        print(f"Failed to send Slack alert: {e}")
        return None

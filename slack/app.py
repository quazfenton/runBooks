#!/usr/bin/env python3
"""
Flask App for Slack Incident Annotation Webhook

This provides a simple webhook endpoint to receive Slack modal submissions
and process incident annotations.
"""

from flask import Flask, request, jsonify
import hmac
import hashlib
import os
from slack.handler import handle_slack_annotation


app = Flask(__name__)

# Get signing secret from environment variable
SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')


def verify_slack_signature(timestamp, signature, body):
    """Verify that the request came from Slack."""
    if not SLACK_SIGNING_SECRET:
        # Raise an error if no secret is set in production
        raise ValueError("SLACK_SIGNING_SECRET environment variable is not set")

    # Verify timestamp to prevent replay attacks (within 5 minutes)
    import time
    if abs(int(time.time()) - int(timestamp)) > 300:
        return False

    sig_basestring = f"v0:{timestamp}:" + body
    expected_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@app.route('/slack/events', methods=['POST'])
def slack_events():
    """Handle Slack events."""
    # Verify the request is from Slack
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')
    
    if not verify_slack_signature(timestamp, signature, request.get_data(as_text=True)):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    
    # Handle URL verification challenge
    if data.get('type') == 'url_verification':
        return data.get('challenge')
    
    # Handle interactive events (modal submissions)
    if data.get('type') == 'block_actions' or data.get('type') == 'view_submission':
        if data.get('type') == 'view_submission' and data.get('view', {}).get('callback_id') == 'incident_annotation':
            response = handle_slack_annotation(data)
            return jsonify(response)
    
    return jsonify({'status': 'ok'})


@app.route('/slack/interactions', methods=['POST'])
def slack_interactions():
    """Handle Slack interactive components."""
    # Verify the request is from Slack
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')
    
    if not verify_slack_signature(timestamp, signature, request.get_data(as_text=True)):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse the payload (Slack sends this as form-encoded)
    payload = request.form.get('payload')
    if payload:
        import json
        data = json.loads(payload)
        
        if data.get('type') == 'view_submission' and data.get('view', {}).get('callback_id') == 'incident_annotation':
            response = handle_slack_annotation(data)
            return jsonify(response)
    
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    import os
    debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('true', '1', 'yes')
    app.run(host='0.0.0.0', port=3000, debug=debug_mode)
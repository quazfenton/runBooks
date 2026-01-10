#!/usr/bin/env python3
"""
Test script for the diagnostics system
"""

import json
import tempfile
from pathlib import Path
from diagnostics import create_diagnostic_record, append_diagnostic_to_runbook

def test_diagnostics():
    # Create a temporary runbook for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        test_runbook = {
            'title': 'Test Runbook',
            'version': '1.0',
            'last_updated': '2026-01-04',
            'owner': 'test-team',
            'steps': [],
            'annotations': [],
            'diagnostics': []
        }
        import yaml
        yaml.dump(test_runbook, f)
        temp_path = Path(f.name)
    
    # Create a test diagnostic record
    test_data = {
        'cpu_usage': 45.2,
        'memory_usage': 67.8,
        'disk_usage': 82.1
    }
    
    diagnostic_record = create_diagnostic_record(
        source='system_monitor',
        query='get_system_metrics',
        result_blob=test_data
    )
    
    # Append to the test runbook
    append_diagnostic_to_runbook(temp_path, diagnostic_record)
    
    # Verify the diagnostic was added
    with open(temp_path, 'r') as f:
        result_runbook = yaml.safe_load(f)
    
    assert len(result_runbook['diagnostics']) == 1
    assert result_runbook['diagnostics'][0]['source'] == 'system_monitor'
    assert result_runbook['diagnostics'][0]['result_blob'] == test_data
    assert 'result_hash' in result_runbook['diagnostics'][0]
    
    print("Diagnostics system test passed!")
    print(f"Created diagnostic with hash: {result_runbook['diagnostics'][0]['result_hash']}")
    
    # Clean up
    temp_path.unlink()

if __name__ == "__main__":
    test_diagnostics()
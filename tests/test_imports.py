#!/usr/bin/env python3
"""
Module Import Verification Test

Verifies all modules can be imported correctly.
Run this first to ensure all dependencies are available.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def test_import(module_name: str, optional: bool = False) -> bool:
    """Test importing a module."""
    try:
        __import__(module_name)
        print(f"[PASS] {module_name}")
        return True
    except ImportError as e:
        if optional:
            print(f"[OPT] {module_name} (optional: {e})")
            return True  # Optional modules can fail
        else:
            print(f"[FAIL] {module_name} ({e})")
            return False


def main():
    """Run all import tests."""
    print("=" * 60)
    print("Living Runbooks - Module Import Verification")
    print("=" * 60)
    print()

    results = {
        'passed': 0,
        'failed': 0,
        'optional': 0
    }

    # Add project root to path explicitly
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Also add the parent directory to ensure all modules are found
    parent_dir = project_root.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    # Core modules
    print("Core Modules:")
    core_modules = [
        ('yaml', False),
        ('requests', False),
        ('pydantic', False),
        ('fastapi', False),
        ('uvicorn', False),
        ('flask', True),  # Optional - only for Slack webhook server
        ('structlog', False)
    ]

    for module_info in core_modules:
        if isinstance(module_info, tuple):
            module, optional = module_info
        else:
            module, optional = module_info, False
            
        if test_import(module, optional=optional):
            results['passed'] += 1
        else:
            results['failed'] += 1

    print()

    # Project modules - use absolute imports from project root
    print("Project Modules:")
    project_modules = [
        ('incident_sources', False),
        ('incident_sources.base', False),
        ('incident_sources.pagerduty', False),
        ('incident_sources.datadog', False),
        ('incident_sources.alertmanager', False),
        ('incident_sources.sentry', False),
        ('ai', False),
        ('ai.llm_suggestion_engine', False),
        ('ai.semantic_correlator', False),
        ('ai.report_generator', False),
        ('version_control', False),
        ('version_control.git_manager', False),
        ('version_control.diff_engine', False),
        ('version_control.rollback', False),
        ('api', False),
        ('api.app', False),
        ('api.routes', False),
        ('api.routes.incidents', True),  # Optional - depends on Flask
        ('slack', False),
        ('slack.handler', False),
        ('slack.app', True),  # Optional - depends on Flask
        ('tests', False),
        ('tests.test_incident_sources', False),
        ('tests.test_integration', False)
    ]

    for module_info in project_modules:
        if isinstance(module_info, tuple):
            module, optional = module_info
        else:
            module, optional = module_info, False
            
        if test_import(module, optional=optional):
            results['passed'] += 1
        else:
            results['failed'] += 1

    print()

    # Optional modules
    print("Optional Modules:")
    optional_modules = [
        ('anthropic', 'Anthropic Claude AI'),
        ('openai', 'OpenAI GPT'),
        ('sentence_transformers', 'Semantic search'),
        ('git', 'Git version control (gitpython)'),
        ('psycopg2', 'PostgreSQL database'),
        ('sqlalchemy', 'SQL ORM'),
        ('redis', 'Redis caching')
    ]

    for module, description in optional_modules:
        if test_import(module, optional=True):
            results['optional'] += 1
        else:
            results['failed'] += 1

    print()
    print("=" * 60)
    print(f"Results: {results['passed']} passed, {results['failed']} failed, {results['optional']} optional")
    print("=" * 60)

    if results['failed'] > 0:
        print("")
        print("[WARNING] Some required modules failed to import.")
        print("Install missing dependencies with:")
        print("  pip install -r requirements.txt")
        return 1

    print("")
    print("[SUCCESS] All required modules imported successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

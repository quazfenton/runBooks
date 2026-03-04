"""
Runbook Diff Engine

Provides detailed comparison of runbook versions.
"""

import yaml
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ChangeType(Enum):
    """Type of change in a runbook."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class RunbookChange:
    """Represents a single change in a runbook."""
    path: str  # JSON path to changed element
    change_type: ChangeType
    old_value: Optional[Any]
    new_value: Optional[Any]
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'type': self.change_type.value,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'description': self.description
        }


class RunbookDiffEngine:
    """
    Compares runbook versions and identifies changes.
    """
    
    def __init__(self):
        """Initialize diff engine."""
        pass
    
    def diff_runbooks(
        self,
        old_runbook: Dict[str, Any],
        new_runbook: Dict[str, Any]
    ) -> List[RunbookChange]:
        """
        Compare two runbook versions and return changes.
        
        Args:
            old_runbook: Previous version
            new_runbook: New version
        
        Returns:
            List of RunbookChange objects
        """
        changes = []
        
        # Compare top-level fields
        all_keys = set(old_runbook.keys()) | set(new_runbook.keys())
        
        for key in all_keys:
            path = f"/{key}"
            old_val = old_runbook.get(key)
            new_val = new_runbook.get(key)
            
            change = self._compare_values(path, old_val, new_val)
            if change and change.change_type != ChangeType.UNCHANGED:
                changes.append(change)
        
        return changes
    
    def _compare_values(
        self,
        path: str,
        old_val: Any,
        new_val: Any
    ) -> Optional[RunbookChange]:
        """Compare two values and return change if different."""
        
        # Both None or equal
        if old_val == new_val:
            return RunbookChange(
                path=path,
                change_type=ChangeType.UNCHANGED,
                old_value=old_val,
                new_value=new_val,
                description="No change"
            )
        
        # Old is None (added)
        if old_val is None:
            return RunbookChange(
                path=path,
                change_type=ChangeType.ADDED,
                old_value=None,
                new_value=new_val,
                description=f"Added: {self._format_value(new_val)}"
            )
        
        # New is None (removed)
        if new_val is None:
            return RunbookChange(
                path=path,
                change_type=ChangeType.REMOVED,
                old_value=old_val,
                new_value=None,
                description=f"Removed: {self._format_value(old_val)}"
            )
        
        # Both are dicts (recurse)
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            return self._diff_dicts(path, old_val, new_val)
        
        # Both are lists (compare as lists)
        if isinstance(old_val, list) and isinstance(new_val, list):
            return self._diff_lists(path, old_val, new_val)
        
        # Simple value change
        return RunbookChange(
            path=path,
            change_type=ChangeType.MODIFIED,
            old_value=old_val,
            new_value=new_val,
            description=f"Changed from {self._format_value(old_val)} to {self._format_value(new_val)}"
        )
    
    def _diff_dicts(
        self,
        path: str,
        old_dict: Dict[str, Any],
        new_dict: Dict[str, Any]
    ) -> Optional[RunbookChange]:
        """Diff two dictionaries."""
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        changes = []
        
        for key in all_keys:
            key_path = f"{path}/{key}"
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            
            change = self._compare_values(key_path, old_val, new_val)
            if change and change.change_type != ChangeType.UNCHANGED:
                changes.append(change)
        
        # Return summary change for the dict
        if changes:
            return RunbookChange(
                path=path,
                change_type=ChangeType.MODIFIED,
                old_value=old_dict,
                new_value=new_dict,
                description=f"Object modified: {len(changes)} changes"
            )
        
        return None
    
    def _diff_lists(
        self,
        path: str,
        old_list: List[Any],
        new_list: List[Any]
    ) -> Optional[RunbookChange]:
        """Diff two lists."""
        
        # Convert to comparable format
        old_set = set(self._make_hashable(item) for item in old_list)
        new_set = set(self._make_hashable(item) for item in new_list)
        
        added = new_set - old_set
        removed = old_set - new_set
        
        if not added and not removed:
            return None
        
        description_parts = []
        if added:
            description_parts.append(f"+{len(added)} items")
        if removed:
            description_parts.append(f"-{len(removed)} items")
        
        return RunbookChange(
            path=path,
            change_type=ChangeType.MODIFIED,
            old_value=old_list,
            new_value=new_list,
            description=", ".join(description_parts)
        )
    
    def _make_hashable(self, item: Any) -> Any:
        """Convert item to hashable format."""
        if isinstance(item, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in item.items()))
        elif isinstance(item, list):
            return tuple(self._make_hashable(i) for i in item)
        return item
    
    def _format_value(self, value: Any) -> str:
        """Format value for display."""
        if value is None:
            return "null"
        
        if isinstance(value, str):
            # Truncate long strings
            if len(value) > 50:
                return value[:47] + "..."
            return f'"{value}"'
        
        if isinstance(value, (int, float, bool)):
            return str(value)
        
        if isinstance(value, (list, dict)):
            return yaml.dump(value, default_flow_style=True).strip()
        
        return str(value)
    
    def diff_files(
        self,
        old_file: Path,
        new_file: Path
    ) -> List[RunbookChange]:
        """
        Diff two runbook files.
        
        Args:
            old_file: Path to old runbook file
            new_file: Path to new runbook file
        
        Returns:
            List of RunbookChange objects
        """
        with open(old_file, 'r', encoding='utf-8') as f:
            old_runbook = yaml.safe_load(f) or {}
        
        with open(new_file, 'r', encoding='utf-8') as f:
            new_runbook = yaml.safe_load(f) or {}
        
        return self.diff_runbooks(old_runbook, new_runbook)
    
    def generate_summary(
        self,
        changes: List[RunbookChange]
    ) -> Dict[str, Any]:
        """
        Generate summary of changes.
        
        Args:
            changes: List of changes
        
        Returns:
            Summary dictionary
        """
        summary = {
            'total_changes': len(changes),
            'added': 0,
            'removed': 0,
            'modified': 0,
            'by_section': {}
        }
        
        for change in changes:
            # Count by type
            if change.change_type == ChangeType.ADDED:
                summary['added'] += 1
            elif change.change_type == ChangeType.REMOVED:
                summary['removed'] += 1
            elif change.change_type == ChangeType.MODIFIED:
                summary['modified'] += 1
            
            # Count by section
            parts = change.path.strip('/').split('/')
            section = parts[0] if parts else 'root'
            
            if section not in summary['by_section']:
                summary['by_section'][section] = 0
            summary['by_section'][section] += 1
        
        return summary
    
    def format_diff_report(
        self,
        changes: List[RunbookChange],
        format: str = 'text'
    ) -> str:
        """
        Format changes as a report.
        
        Args:
            changes: List of changes
            format: Output format ('text', 'markdown', 'json')
        
        Returns:
            Formatted report
        """
        if format == 'json':
            import json
            return json.dumps([c.to_dict() for c in changes], indent=2)
        
        elif format == 'markdown':
            lines = ["# Runbook Changes\n"]
            
            for change in changes:
                icon = {
                    ChangeType.ADDED: "➕",
                    ChangeType.REMOVED: "❌",
                    ChangeType.MODIFIED: "✏️"
                }.get(change.change_type, "•")
                
                lines.append(f"{icon} **{change.path}**")
                lines.append(f"   {change.description}\n")
            
            return "\n".join(lines)
        
        else:  # text
            lines = ["Runbook Changes:", "=" * 50]
            
            for change in changes:
                prefix = {
                    ChangeType.ADDED: "+",
                    ChangeType.REMOVED: "-",
                    ChangeType.MODIFIED: "~"
                }.get(change.change_type, " ")
                
                lines.append(f"[{prefix}] {change.path}")
                lines.append(f"    {change.description}")
            
            return "\n".join(lines)


def main():
    """Example usage of RunbookDiffEngine."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compare runbook versions"
    )
    parser.add_argument(
        "--old",
        required=True,
        help="Path to old runbook file"
    )
    parser.add_argument(
        "--new",
        required=True,
        help="Path to new runbook file"
    )
    parser.add_argument(
        "--format",
        choices=['text', 'markdown', 'json'],
        default='text',
        help="Output format"
    )
    parser.add_argument(
        "--summary",
        action='store_true',
        help="Show summary only"
    )
    
    args = parser.parse_args()
    
    engine = RunbookDiffEngine()
    
    # Diff files
    changes = engine.diff_files(Path(args.old), Path(args.new))
    
    if args.summary:
        summary = engine.generate_summary(changes)
        print(f"Total changes: {summary['total_changes']}")
        print(f"  Added: {summary['added']}")
        print(f"  Removed: {summary['removed']}")
        print(f"  Modified: {summary['modified']}")
        print(f"\nBy section:")
        for section, count in summary['by_section'].items():
            print(f"  {section}: {count}")
    else:
        report = engine.format_diff_report(changes, format=args.format)
        print(report)


if __name__ == "__main__":
    main()

"""
Runbook Rollback Module

Provides capability to rollback runbooks to previous versions.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import tempfile
import os

try:
    from git import Repo, GitCommandError
    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False


class RunbookRollback:
    """
    Handles rollback of runbooks to previous versions.
    """
    
    def __init__(self, repo_path: str = "."):
        """
        Initialize rollback handler.
        
        Args:
            repo_path: Path to git repository root
        """
        self.repo_path = Path(repo_path).resolve()
        
        if GITPYTHON_AVAILABLE and (self.repo_path / ".git").exists():
            self.repo = Repo(self.repo_path)
        else:
            self.repo = None
    
    def get_available_versions(
        self,
        runbook_path: str
    ) -> List[Dict[str, Any]]:
        """
        Get all available versions of a runbook.
        
        Args:
            runbook_path: Path to runbook
        
        Returns:
            List of version info dicts
        """
        if not self.repo:
            return []
        
        runbook_file = self.repo_path / runbook_path
        
        versions = []
        
        try:
            for commit in self.repo.iter_commits(
                paths=str(runbook_file),
                max_count=100
            ):
                # Check if file exists in this commit
                try:
                    blob = commit[str(runbook_file)]
                    
                    # Get annotation count if available
                    content = blob.data_stream.read().decode('utf-8')
                    runbook_data = yaml.safe_load(content) or {}
                    annotation_count = len(runbook_data.get('annotations', []))
                    
                    versions.append({
                        'commit': commit.hexsha,
                        'short_commit': commit.hexsha[:7],
                        'timestamp': datetime.fromtimestamp(
                            commit.committed_date
                        ).isoformat(),
                        'author': commit.author.name,
                        'message': commit.message.strip().split('\n')[0],
                        'annotation_count': annotation_count,
                        'is_current': False
                    })
                except KeyError:
                    # File doesn't exist in this commit
                    continue
        except GitCommandError:
            return []
        
        # Mark current version
        if versions:
            versions[0]['is_current'] = True
        
        return versions
    
    def rollback_to_commit(
        self,
        runbook_path: str,
        target_commit: str,
        create_backup: bool = True,
        commit_message: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Rollback runbook to a specific commit.
        
        Args:
            runbook_path: Path to runbook
            target_commit: Commit hash to rollback to
            create_backup: If True, create backup before rollback
            commit_message: Optional custom commit message
        
        Returns:
            (success, message, backup_path) tuple
        """
        if not self.repo:
            return False, "Git repository not found", None
        
        runbook_file = self.repo_path / runbook_path
        
        # Verify target commit exists
        try:
            target_blob = self.repo.commit(target_commit)[str(runbook_file)]
        except (KeyError, GitCommandError) as e:
            return False, f"Target commit not found or file doesn't exist: {e}", None
        
        # Create backup if requested
        backup_path = None
        if create_backup and runbook_file.exists():
            backup_path = self._create_backup(runbook_file)
        
        # Get content from target commit
        content = target_blob.data_stream.read().decode('utf-8')
        
        # Write content to file
        try:
            with open(runbook_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except IOError as e:
            return False, f"Failed to write rollback: {e}", backup_path
        
        # Commit the rollback
        if commit_message is None:
            commit_message = f"rollback: {runbook_path} to {target_commit[:7]}"
        
        try:
            self.repo.index.add([str(runbook_file)])
            self.repo.index.commit(
                commit_message,
                author=self.repo.active_branch.commit.author
            )
            
            return True, f"Successfully rolled back to {target_commit[:7]}", backup_path
        
        except GitCommandError as e:
            # Try to restore from backup
            if backup_path:
                self._restore_backup(runbook_file, backup_path)
            
            return False, f"Failed to commit rollback: {e}", backup_path
    
    def rollback_annotations(
        self,
        runbook_path: str,
        keep_last_n: int
    ) -> Tuple[bool, str, int]:
        """
        Rollback to keep only the last N annotations.
        
        Args:
            runbook_path: Path to runbook
            keep_last_n: Number of recent annotations to keep
        
        Returns:
            (success, message, removed_count) tuple
        """
        runbook_file = self.repo_path / runbook_path
        
        if not runbook_file.exists():
            return False, "Runbook file not found", 0
        
        # Load runbook
        with open(runbook_file, 'r', encoding='utf-8') as f:
            runbook = yaml.safe_load(f) or {}
        
        annotations = runbook.get('annotations', [])
        
        if len(annotations) <= keep_last_n:
            return True, f"Already has {len(annotations)} annotations (≤ {keep_last_n})", 0
        
        # Keep only last N
        removed_count = len(annotations) - keep_last_n
        runbook['annotations'] = annotations[-keep_last_n:]
        
        # Write back
        backup_path = self._create_backup(runbook_file)
        
        try:
            with open(runbook_file, 'w', encoding='utf-8') as f:
                yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
            
            # Commit if git available
            if self.repo:
                self.repo.index.add([str(runbook_file)])
                self.repo.index.commit(
                    f"rollback: removed {removed_count} old annotations from {runbook_path}"
                )
            
            return True, f"Removed {removed_count} annotations", backup_path
        
        except Exception as e:
            # Restore backup on error
            if backup_path:
                self._restore_backup(runbook_file, backup_path)
            
            return False, f"Failed to rollback annotations: {e}", 0
    
    def remove_annotation(
        self,
        runbook_path: str,
        incident_id: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Remove a specific annotation by incident ID.
        
        Args:
            runbook_path: Path to runbook
            incident_id: Incident ID to remove
        
        Returns:
            (success, message, backup_path) tuple
        """
        runbook_file = self.repo_path / runbook_path
        
        if not runbook_file.exists():
            return False, "Runbook file not found", None
        
        # Load runbook
        with open(runbook_file, 'r', encoding='utf-8') as f:
            runbook = yaml.safe_load(f) or {}
        
        annotations = runbook.get('annotations', [])
        
        # Find and remove annotation
        original_count = len(annotations)
        annotations = [
            a for a in annotations
            if a.get('incident_id') != incident_id
        ]
        
        if len(annotations) == original_count:
            return False, f"Annotation with incident_id '{incident_id}' not found", None
        
        runbook['annotations'] = annotations
        
        # Create backup
        backup_path = self._create_backup(runbook_file)
        
        try:
            with open(runbook_file, 'w', encoding='utf-8') as f:
                yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
            
            # Commit if git available
            if self.repo:
                self.repo.index.add([str(runbook_file)])
                self.repo.index.commit(
                    f"rollback: removed annotation {incident_id} from {runbook_path}"
                )
            
            return True, f"Removed annotation {incident_id}", backup_path
        
        except Exception as e:
            if backup_path:
                self._restore_backup(runbook_file, backup_path)
            
            return False, f"Failed to remove annotation: {e}", backup_path
    
    def _create_backup(self, file_path: Path) -> str:
        """Create backup of file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.name}.backup_{timestamp}"
        backup_path = file_path.parent / backup_name
        
        with open(file_path, 'r', encoding='utf-8') as src:
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        
        return str(backup_path)
    
    def _restore_backup(self, file_path: Path, backup_path: str):
        """Restore file from backup."""
        with open(backup_path, 'r', encoding='utf-8') as src:
            with open(file_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
    
    def list_backups(self, runbook_path: str) -> List[str]:
        """
        List available backups for a runbook.
        
        Args:
            runbook_path: Path to runbook
        
        Returns:
            List of backup file paths
        """
        runbook_file = self.repo_path / runbook_path
        backup_dir = runbook_file.parent
        
        backups = []
        for f in backup_dir.glob(f"{runbook_file.name}.backup_*"):
            backups.append(str(f))
        
        return sorted(backups, reverse=True)
    
    def restore_backup(
        self,
        runbook_path: str,
        backup_path: str
    ) -> Tuple[bool, str]:
        """
        Restore runbook from backup.
        
        Args:
            runbook_path: Path to runbook
            backup_path: Path to backup file
        
        Returns:
            (success, message) tuple
        """
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            return False, f"Backup not found: {backup_path}"
        
        runbook_file = self.repo_path / runbook_path
        
        try:
            self._restore_backup(runbook_file, backup_path)
            
            # Commit if git available
            if self.repo:
                self.repo.index.add([str(runbook_file)])
                self.repo.index.commit(
                    f"restore: {runbook_path} from backup {backup_file.name}"
                )
            
            return True, f"Restored from backup {backup_file.name}"
        
        except Exception as e:
            return False, f"Failed to restore backup: {e}"
    
    def cleanup_backups(
        self,
        runbook_path: str,
        keep_last: int = 3
    ) -> int:
        """
        Clean up old backups.
        
        Args:
            runbook_path: Path to runbook
            keep_last: Number of recent backups to keep
        
        Returns:
            Number of backups removed
        """
        backups = self.list_backups(runbook_path)
        
        if len(backups) <= keep_last:
            return 0
        
        removed = 0
        for backup in backups[keep_last:]:
            try:
                os.unlink(backup)
                removed += 1
            except OSError:
                pass
        
        return removed


def main():
    """Example usage of RunbookRollback."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rollback runbooks to previous versions"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to git repository"
    )
    parser.add_argument(
        "--runbook",
        required=True,
        help="Path to runbook"
    )
    parser.add_argument(
        "--action",
        choices=['versions', 'rollback', 'annotations', 'remove', 'backups', 'restore'],
        required=True,
        help="Action to perform"
    )
    parser.add_argument(
        "--commit",
        help="Target commit hash (for rollback)"
    )
    parser.add_argument(
        "--keep",
        type=int,
        help="Number of annotations to keep (for annotations action)"
    )
    parser.add_argument(
        "--incident-id",
        help="Incident ID to remove (for remove action)"
    )
    parser.add_argument(
        "--backup",
        help="Backup file path (for restore action)"
    )
    parser.add_argument(
        "--no-backup",
        action='store_true',
        help="Don't create backup before rollback"
    )
    
    args = parser.parse_args()
    
    rollback = RunbookRollback(args.repo)
    
    if args.action == 'versions':
        versions = rollback.get_available_versions(args.runbook)
        
        if not versions:
            print("No versions found (git not available or no history)")
            return
        
        print(f"Available versions of {args.runbook}:\n")
        for v in versions:
            marker = " (current)" if v['is_current'] else ""
            print(f"  {v['short_commit']} | {v['timestamp'][:10]} | {v['author']}")
            print(f"    {v['message']}{marker}")
            print(f"    Annotations: {v['annotation_count']}")
            print()
    
    elif args.action == 'rollback':
        if not args.commit:
            print("Error: --commit required for rollback")
            return
        
        success, message, backup = rollback.rollback_to_commit(
            args.runbook,
            args.commit,
            create_backup=not args.no_backup
        )
        
        print(f"{'✓' if success else '✗'} {message}")
        if backup:
            print(f"  Backup: {backup}")
    
    elif args.action == 'annotations':
        if not args.keep:
            print("Error: --keep required for annotations action")
            return
        
        success, message, count = rollback.rollback_annotations(args.runbook, args.keep)
        print(f"{'✓' if success else '✗'} {message}")
        if isinstance(count, int) and count > 0:
            print(f"  Removed {count} annotations")
    
    elif args.action == 'remove':
        if not args.incident_id:
            print("Error: --incident-id required for remove action")
            return
        
        success, message, backup = rollback.remove_annotation(
            args.runbook,
            args.incident_id
        )
        print(f"{'✓' if success else '✗'} {message}")
        if backup:
            print(f"  Backup: {backup}")
    
    elif args.action == 'backups':
        backups = rollback.list_backups(args.runbook)
        
        if not backups:
            print("No backups found")
            return
        
        print(f"Available backups for {args.runbook}:\n")
        for b in backups:
            print(f"  {b}")
    
    elif args.action == 'restore':
        if not args.backup:
            print("Error: --backup required for restore action")
            return
        
        success, message = rollback.restore_backup(args.runbook, args.backup)
        print(f"{'✓' if success else '✗'} {message}")


if __name__ == "__main__":
    main()

"""
Git Version Control for Runbooks

Provides git-backed versioning for runbook changes with audit trails.
Requires gitpython: pip install gitpython

SECURITY ENHANCED: Added retry logic for transient failures
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import yaml
import time
from functools import wraps

try:
    from git import Repo, Actor, GitCommandError
    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False
    print("Warning: gitpython not installed. Install with: pip install gitpython")


def retry_on_git_error(max_attempts=3, delay=1.0, backoff=2.0):
    """
    Decorator to retry git operations on transient failures.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay (exponential backoff)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except GitCommandError as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Git operation failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Git operation failed after {max_attempts} attempts: {e}")
                        raise
                except Exception as e:
                    # Non-retryable error
                    logger.error(f"Non-retryable error in git operation: {e}")
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class RunbookVersionControl:
    """
    Manages git versioning for runbooks.
    
    Every annotation or change is committed with structured metadata.
    """
    
    def __init__(self, repo_path: str = "."):
        """
        Initialize runbook version control.
        
        Args:
            repo_path: Path to git repository root
        """
        if not GITPYTHON_AVAILABLE:
            raise ImportError(
                "gitpython package not installed. "
                "Install with: pip install gitpython"
            )
        
        self.repo_path = Path(repo_path).resolve()
        
        # Initialize or open repo
        if (self.repo_path / ".git").exists():
            self.repo = Repo(self.repo_path)
        else:
            self.repo = Repo.init(self.repo_path)
        
        # Actor for automated commits
        self.actor = Actor(
            name="runbook-bot",
            email="runbook-bot@runbooks.local"
        )
    
    @retry_on_git_error(max_attempts=3, delay=1.0, backoff=2.0)
    def commit_annotation(
        self,
        runbook_path: str,
        annotation: Dict[str, Any],
        author: Optional[str] = None,
        commit_message: Optional[str] = None
    ) -> str:
        """
        Append annotation and commit to git.

        Args:
            runbook_path: Path to runbook YAML
            annotation: Annotation to append
            author: Optional human author name
            commit_message: Optional custom commit message

        Returns:
            Commit hash
        """
        runbook_file = self.repo_path / runbook_path

        if not runbook_file.exists():
            raise FileNotFoundError(f"Runbook not found: {runbook_file}")

        # Append annotation
        self._append_annotation(runbook_file, annotation)

        # Create commit message
        if commit_message:
            msg = commit_message
        else:
            msg = self._build_commit_message(annotation, author)

        # Stage and commit
        self.repo.index.add([str(runbook_file)])

        commit = self.repo.index.commit(
            msg,
            author=self.actor if not author else Actor(author, f"{author}@runbooks.local"),
            committer=self.actor
        )

        return commit.hexsha
    
    def _append_annotation(self, runbook_file: Path, annotation: Dict[str, Any]):
        """Append annotation to runbook file."""
        with open(runbook_file, 'r', encoding='utf-8') as f:
            runbook = yaml.safe_load(f)
        
        if not runbook:
            runbook = {}
        
        if 'annotations' not in runbook:
            runbook['annotations'] = []
        
        if not isinstance(runbook['annotations'], list):
            runbook['annotations'] = []
        
        runbook['annotations'].append(annotation)
        
        with open(runbook_file, 'w', encoding='utf-8') as f:
            yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
    
    def _build_commit_message(
        self,
        annotation: Dict[str, Any],
        author: Optional[str]
    ) -> str:
        """Build structured commit message."""
        incident_id = annotation.get('incident_id', 'UNKNOWN')
        cause = annotation.get('cause', 'Unknown cause')[:50]
        fix = annotation.get('fix', 'Unknown fix')[:50]
        
        msg = f"""incident: {incident_id}

cause: {cause}
fix: {fix}

"""
        
        if author:
            msg += f"Annotated by: {author}\n"
        
        return msg
    
    def commit_runbook_change(
        self,
        runbook_path: str,
        change_type: str,
        description: str,
        author: Optional[str] = None
    ) -> str:
        """
        Commit a runbook change (not annotation).
        
        Args:
            runbook_path: Path to runbook
            change_type: Type of change (UPDATE, CREATE, DELETE)
            description: Description of changes
            author: Optional author name
        
        Returns:
            Commit hash
        """
        runbook_file = self.repo_path / runbook_path
        
        # Stage changes
        if runbook_file.exists():
            self.repo.index.add([str(runbook_file)])
        else:
            # File was deleted
            self.repo.index.remove([str(runbook_file)], r=True)
        
        msg = f"""{change_type}: {runbook_path}

{description}
"""
        
        commit = self.repo.index.commit(
            msg,
            author=self.actor if not author else Actor(author, f"{author}@runbooks.local"),
            committer=self.actor
        )
        
        return commit.hexsha
    
    def get_runbook_history(
        self,
        runbook_path: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get commit history for a runbook.
        
        Args:
            runbook_path: Path to runbook
            limit: Maximum commits to return
        
        Returns:
            List of commit info dicts
        """
        runbook_file = self.repo_path / runbook_path
        
        commits = []
        
        try:
            for commit in self.repo.iter_commits(
                paths=str(runbook_file),
                max_count=limit
            ):
                # Get stats for this commit
                stats = commit.stats.files.get(str(runbook_file), {})
                
                commits.append({
                    'hash': commit.hexsha,
                    'short_hash': commit.hexsha[:7],
                    'author': commit.author.name,
                    'email': commit.author.email,
                    'message': commit.message.strip(),
                    'timestamp': datetime.fromtimestamp(
                        commit.committed_date
                    ).isoformat(),
                    'additions': stats.get('insertions', 0),
                    'deletions': stats.get('deletions', 0),
                    'lines_changed': stats.get('lines', 0)
                })
        except GitCommandError as e:
            if "unknown revision" in str(e).lower():
                # File has no history
                return []
            raise
        
        return commits
    
    def get_commit_diff(self, commit_hash: str) -> Dict[str, Any]:
        """
        Get diff for a specific commit.
        
        Args:
            commit_hash: Git commit hash
        
        Returns:
            Diff information
        """
        commit = self.repo.commit(commit_hash)
        parent = commit.parents[0] if commit.parents else None
        
        diff = parent.diff(commit) if parent else commit.diff()
        
        changes = []
        for d in diff:
            change_info = {
                'path': d.b_path or d.a_path,
                'type': 'modified'
            }
            
            if d.a_blob and d.b_blob:
                change_info['type'] = 'modified'
                change_info['additions'] = d.diff.count('\n+') if d.diff else 0
                change_info['deletions'] = d.diff.count('\n-') if d.diff else 0
            elif d.b_blob:
                change_info['type'] = 'added'
            elif d.a_blob:
                change_info['type'] = 'deleted'
            
            changes.append(change_info)
        
        return {
            'commit': commit_hash,
            'author': commit.author.name,
            'message': commit.message.strip(),
            'timestamp': datetime.fromtimestamp(commit.committed_date).isoformat(),
            'changes': changes
        }
    
    def get_commit_content(
        self,
        commit_hash: str,
        runbook_path: str
    ) -> Dict[str, Any]:
        """
        Get runbook content at a specific commit.
        
        Args:
            commit_hash: Git commit hash
            runbook_path: Path to runbook
        
        Returns:
            Runbook content at that commit
        """
        try:
            blob = self.repo.commit(commit_hash)[runbook_path]
            content = blob.data_stream.read().decode('utf-8')
            runbook_data = yaml.safe_load(content)
            
            return {
                'commit': commit_hash,
                'path': runbook_path,
                'content': runbook_data or {},
                'raw': content
            }
        except KeyError:
            raise FileNotFoundError(
                f"Runbook {runbook_path} not found at commit {commit_hash}"
            )
    
    def create_branch(
        self,
        branch_name: str,
        from_commit: Optional[str] = None,
        checkout: bool = False
    ) -> str:
        """
        Create a new branch for runbook changes.
        
        Args:
            branch_name: Name for new branch
            from_commit: Optional commit to branch from (default: HEAD)
            checkout: If True, checkout the new branch
        
        Returns:
            Branch name
        """
        self.repo.git.branch(
            branch_name,
            from_commit or 'HEAD'
        )
        
        if checkout:
            self.repo.git.checkout(branch_name)
        
        return branch_name
    
    def merge_branch(
        self,
        source_branch: str,
        target_branch: str = "main",
        commit_message: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Merge a branch into target.
        
        Args:
            source_branch: Branch to merge from
            target_branch: Branch to merge into
            commit_message: Optional merge commit message
        
        Returns:
            (success, message) tuple
        """
        try:
            # Checkout target
            self.repo.git.checkout(target_branch)
            
            # Merge
            merge_kwargs = {'--no-ff': True}
            if commit_message:
                merge_kwargs['-m'] = commit_message
            else:
                merge_kwargs['-m'] = f"Merge {source_branch} into {target_branch}"
            
            self.repo.git.merge(source_branch, **merge_kwargs)
            
            return True, f"Successfully merged {source_branch} into {target_branch}"
        
        except GitCommandError as e:
            error_msg = str(e)
            
            if 'conflict' in error_msg.lower():
                # Abort merge on conflict
                try:
                    self.repo.git.merge('--abort')
                except:
                    pass
                return False, f"Merge conflict detected. Merge aborted."
            
            return False, f"Merge failed: {error_msg}"
    
    def get_uncommitted_changes(self, runbook_path: Optional[str] = None) -> List[str]:
        """
        Get list of uncommitted changes.
        
        Args:
            runbook_path: Optional path to filter changes
        
        Returns:
            List of changed file paths
        """
        changes = []
        
        # Staged changes
        staged = self.repo.index.diff("HEAD")
        for diff in staged:
            if runbook_path is None or runbook_path in diff.a_path or runbook_path in diff.b_path:
                changes.append(diff.b_path or diff.a_path)
        
        # Unstaged changes
        unstaged = self.repo.index.diff(None)
        for diff in unstaged:
            if runbook_path is None or runbook_path in diff.a_path or runbook_path in diff.b_path:
                if diff.b_path not in changes:
                    changes.append(diff.b_path or diff.a_path)
        
        return changes
    
    def is_clean(self) -> bool:
        """Check if repository has no uncommitted changes."""
        return len(self.repo.index.diff(None)) == 0 and len(self.repo.index.diff("HEAD")) == 0
    
    def get_current_branch(self) -> str:
        """Get current branch name."""
        return self.repo.active_branch.name
    
    def get_tags(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get list of tags.
        
        Args:
            pattern: Optional pattern to filter tags
        
        Returns:
            List of tag names
        """
        tags = [tag.name for tag in self.repo.tags]
        
        if pattern:
            import fnmatch
            tags = [t for t in tags if fnmatch.fnmatch(t, pattern)]
        
        return tags
    
    def create_tag(
        self,
        tag_name: str,
        commit_hash: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """
        Create a tag.
        
        Args:
            tag_name: Tag name
            commit_hash: Commit to tag (default: HEAD)
            message: Optional tag message
        
        Returns:
            Tag name
        """
        kwargs = {}
        if message:
            kwargs['-m'] = message
        
        self.repo.git.tag(
            tag_name,
            commit_hash or 'HEAD',
            **kwargs
        )
        
        return tag_name


def main():
    """Example usage of RunbookVersionControl."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description="Git version control for runbooks"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to git repository"
    )
    parser.add_argument(
        "--runbook",
        help="Path to runbook"
    )
    parser.add_argument(
        "--action",
        choices=['history', 'diff', 'content', 'branch', 'tag'],
        default='history',
        help="Action to perform"
    )
    parser.add_argument(
        "--commit",
        help="Commit hash (for diff/content actions)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit for history action"
    )
    parser.add_argument(
        "--output",
        choices=['json', 'text'],
        default='text',
        help="Output format"
    )
    
    args = parser.parse_args()
    
    if not GITPYTHON_AVAILABLE:
        print("Error: gitpython not installed")
        print("Install with: pip install gitpython")
        return
    
    try:
        vcs = RunbookVersionControl(args.repo)
        
        if args.action == 'history':
            if not args.runbook:
                print("Error: --runbook required for history action")
                return
            
            history = vcs.get_runbook_history(args.runbook, limit=args.limit)
            
            if args.output == 'json':
                print(json.dumps(history, indent=2))
            else:
                for commit in history:
                    print(f"{commit['short_hash']} | {commit['timestamp'][:10]} | {commit['author']}")
                    print(f"  {commit['message'].split(chr(10))[0]}")
                    print()
        
        elif args.action == 'diff':
            if not args.commit:
                print("Error: --commit required for diff action")
                return
            
            diff = vcs.get_commit_diff(args.commit)
            
            if args.output == 'json':
                print(json.dumps(diff, indent=2))
            else:
                print(f"Commit: {diff['commit']}")
                print(f"Author: {diff['author']}")
                print(f"Date: {diff['timestamp']}")
                print(f"Message: {diff['message']}")
                print("\nChanges:")
                for change in diff['changes']:
                    print(f"  [{change['type']}] {change['path']}")
        
        elif args.action == 'content':
            if not args.commit or not args.runbook:
                print("Error: --commit and --runbook required for content action")
                return
            
            content = vcs.get_commit_content(args.commit, args.runbook)
            
            if args.output == 'json':
                print(json.dumps(content['content'], indent=2))
            else:
                print(f"Content of {args.runbook} at {args.commit}:")
                print(content['raw'])
        
        elif args.action == 'branch':
            branch = vcs.get_current_branch()
            print(f"Current branch: {branch}")
        
        elif args.action == 'tag':
            tags = vcs.get_tags()
            print("Tags:")
            for tag in tags:
                print(f"  {tag}")
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

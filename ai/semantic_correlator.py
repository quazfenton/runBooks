"""
Semantic Incident Correlation Engine

Uses sentence embeddings to find similar incidents across services.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import yaml
from dataclasses import dataclass, field

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print(
        "Warning: sentence-transformers not installed. "
        "Install with: pip install sentence-transformers"
    )


@dataclass
class IncidentEmbedding:
    """Represents an incident with its embedding."""
    incident_id: str
    service: str
    text: str  # Original text used for embedding
    embedding: np.ndarray = field(repr=False)  # Don't show array in repr
    timestamp: str
    cause: str
    fix: str
    
    def __post_init__(self):
        """Validate embedding is numpy array."""
        if not isinstance(self.embedding, np.ndarray):
            self.embedding = np.array(self.embedding)


class SemanticCorrelator:
    """
    Finds semantically similar incidents using embeddings.
    
    Uses SentenceTransformers for efficient, accurate semantic similarity.
    Default model: all-MiniLM-L6-v2 (fast, good quality, 80MB)
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize semantic correlator.
        
        Args:
            model_name: SentenceTransformer model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            self.model = None
            print(
                "SemanticCorrelator initialized without model. "
                "Install sentence-transformers for full functionality."
            )
            return
        
        self.model = SentenceTransformer(model_name)
        self.embeddings: Dict[str, IncidentEmbedding] = {}
    
    def embed_incident(
        self,
        incident_id: str,
        cause: str,
        fix: str,
        symptoms: Optional[List[str]] = None,
        service: str = "unknown",
        timestamp: str = ""
    ) -> Optional[IncidentEmbedding]:
        """
        Create embedding for an incident.
        
        Args:
            incident_id: Unique incident identifier
            cause: Root cause text
            fix: Fix applied
            symptoms: List of symptoms
            service: Service name
            timestamp: Incident timestamp
        
        Returns:
            IncidentEmbedding object or None if model not available
        """
        if not self.model:
            return None
        
        # Combine all text for embedding
        text_parts = [cause, fix]
        if symptoms:
            text_parts.extend(symptoms)
        
        text = " ".join(text_parts)
        
        # Generate embedding
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        incident_emb = IncidentEmbedding(
            incident_id=incident_id,
            service=service,
            text=text,
            embedding=embedding,
            timestamp=timestamp,
            cause=cause,
            fix=fix
        )
        
        # Store in memory
        key = f"{service}:{incident_id}"
        self.embeddings[key] = incident_emb
        
        return incident_emb
    
    def find_similar_incidents(
        self,
        query_incident: IncidentEmbedding,
        threshold: float = 0.7,
        max_results: int = 10,
        exclude_service: bool = False
    ) -> List[Tuple[IncidentEmbedding, float]]:
        """
        Find incidents similar to the query.
        
        Args:
            query_incident: Query incident embedding
            threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results
            exclude_service: If True, exclude incidents from same service
        
        Returns:
            List of (incident, similarity_score) tuples
        """
        if not self.model or not self.embeddings:
            return []
        
        query_embedding = query_incident.embedding
        
        similar = []
        for key, incident in self.embeddings.items():
            # Skip if excluding same service
            if exclude_service and incident.service == query_incident.service:
                continue
            
            # Skip self
            if key == f"{query_incident.service}:{query_incident.incident_id}":
                continue
            
            # Calculate cosine similarity
            similarity = util.cos_sim(
                query_embedding.reshape(1, -1),
                incident.embedding.reshape(1, -1)
            ).item()
            
            if similarity >= threshold:
                similar.append((incident, similarity))
        
        # Sort by similarity (descending)
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return similar[:max_results]
    
    def load_runbook_annotations(
        self,
        runbook_dir: Path,
        verbose: bool = True
    ) -> int:
        """
        Load all annotations from runbooks and create embeddings.
        
        Args:
            runbook_dir: Directory containing runbooks
            verbose: Print progress messages
        
        Returns:
            Number of annotations loaded
        """
        if not self.model:
            if verbose:
                print("Cannot load annotations: model not available")
            return 0
        
        count = 0
        errors = 0
        
        for runbook_file in runbook_dir.rglob("runbook.yaml"):
            try:
                with open(runbook_file, 'r', encoding='utf-8') as f:
                    runbook = yaml.safe_load(f)
                
                if not runbook or not isinstance(runbook, dict):
                    continue
                
                service = runbook_file.parent.name
                annotations = runbook.get('annotations', [])
                
                if not isinstance(annotations, list):
                    continue
                
                for annotation in annotations:
                    if not isinstance(annotation, dict):
                        continue
                    
                    incident_id = annotation.get(
                        'incident_id',
                        f"{service}:{len(self.embeddings)}"
                    )
                    
                    self.embed_incident(
                        incident_id=incident_id,
                        cause=annotation.get('cause', ''),
                        fix=annotation.get('fix', ''),
                        symptoms=annotation.get('symptoms', []),
                        service=service,
                        timestamp=annotation.get('timestamp', '')
                    )
                    count += 1
            
            except Exception as e:
                errors += 1
                if verbose:
                    print(f"Error loading {runbook_file}: {e}")
                continue
        
        if verbose:
            print(f"Loaded {count} incident annotations from {runbook_dir}")
            if errors > 0:
                print(f"  ({errors} errors)")
        
        return count
    
    def detect_cascade_pattern(
        self,
        incidents: List[IncidentEmbedding],
        time_window_minutes: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if multiple incidents are part of a cascade failure.
        
        Args:
            incidents: List of incidents to analyze
            time_window_minutes: Time window for cascade detection
        
        Returns:
            Cascade pattern info if detected, None otherwise
        """
        if not incidents or len(incidents) < 2:
            return None
        
        from datetime import datetime, timedelta
        
        # Sort by timestamp
        try:
            sorted_incidents = sorted(
                incidents,
                key=lambda x: x.timestamp
            )
        except (TypeError, ValueError):
            return None
        
        # Check for temporal clustering
        cascade_groups = []
        current_group = [sorted_incidents[0]]
        
        for incident in sorted_incidents[1:]:
            try:
                time_diff = (
                    datetime.fromisoformat(
                        incident.timestamp.replace('Z', '+00:00')
                    ) -
                    datetime.fromisoformat(
                        current_group[-1].timestamp.replace('Z', '+00:00')
                    )
                )
                
                if time_diff <= timedelta(minutes=time_window_minutes):
                    current_group.append(incident)
                else:
                    if len(current_group) >= 2:
                        cascade_groups.append(current_group)
                    current_group = [incident]
            
            except (ValueError, TypeError):
                continue
        
        if len(current_group) >= 2:
            cascade_groups.append(current_group)
        
        if not cascade_groups:
            return None
        
        # Return largest cascade
        largest_cascade = max(cascade_groups, key=len)
        
        return {
            'incident_count': len(largest_cascade),
            'services_affected': list(
                set(i.service for i in largest_cascade)
            ),
            'time_span_minutes': (
                datetime.fromisoformat(
                    largest_cascade[-1].timestamp.replace('Z', '+00:00')
                ) -
                datetime.fromisoformat(
                    largest_cascade[0].timestamp.replace('Z', '+00:00')
                )
            ).total_seconds() / 60,
            'common_themes': self._extract_common_themes(largest_cascade)
        }
    
    def _extract_common_themes(
        self,
        incidents: List[IncidentEmbedding]
    ) -> List[str]:
        """Extract common themes from cascade incidents."""
        # Simple keyword extraction
        keywords = []
        for incident in incidents:
            keywords.extend(incident.cause.lower().split())
            keywords.extend(incident.fix.lower().split())
        
        from collections import Counter
        
        word_counts = Counter(keywords)
        
        # Return top 5 most common words (excluding stopwords)
        stopwords = {
            'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
            'of', 'and', 'or', 'is', 'was', 'were', 'been',
            'with', 'from', 'by', 'as', 'it', 'this', 'that'
        }
        
        common = [
            word for word, count in word_counts.most_common(10)
            if word not in stopwords and len(word) > 2
        ]
        
        return common[:5]
    
    def get_cross_service_patterns(
        self,
        min_occurrences: int = 2
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Find patterns that appear across multiple services.
        
        Args:
            min_occurrences: Minimum times a pattern must appear
        
        Returns:
            Dict mapping cause/fix patterns to list of (service, similarity)
        """
        if not self.embeddings:
            return {}
        
        patterns = {}
        
        # Group by similar embeddings
        for key1, emb1 in self.embeddings.items():
            service1 = emb1.service
            
            for key2, emb2 in self.embeddings.items():
                if key1 >= key2:  # Avoid duplicates
                    continue
                
                similarity = util.cos_sim(
                    emb1.embedding.reshape(1, -1),
                    emb2.embedding.reshape(1, -1)
                ).item()
                
                if similarity >= 0.8:  # High similarity threshold
                    # Extract common cause pattern
                    pattern = self._extract_common_pattern(emb1.cause, emb2.cause)
                    
                    if pattern:
                        if pattern not in patterns:
                            patterns[pattern] = []
                        
                        patterns[pattern].append((service1, similarity))
                        if emb2.service != service1:
                            patterns[pattern].append((emb2.service, similarity))
        
        # Filter by min occurrences
        return {
            pattern: services
            for pattern, services in patterns.items()
            if len(services) >= min_occurrences
        }
    
    def _extract_common_pattern(self, text1: str, text2: str) -> Optional[str]:
        """Extract common pattern from two texts."""
        # Simple approach: find common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        common = words1 & words2
        
        # Filter stopwords
        stopwords = {
            'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
            'of', 'and', 'or', 'is', 'was', 'were', 'been'
        }
        common = [w for w in common if w not in stopwords and len(w) > 2]
        
        if len(common) >= 2:
            return ' '.join(common)
        
        return None


def main():
    """Example usage of semantic correlator."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Find similar incidents using semantic search"
    )
    parser.add_argument(
        "--runbooks-dir",
        default="runbooks",
        help="Directory containing runbooks"
    )
    parser.add_argument(
        "--query",
        help="Query text (cause/fix description)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Similarity threshold"
    )
    parser.add_argument(
        "--service",
        help="Filter by service name"
    )
    
    args = parser.parse_args()
    
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print(
            "Error: sentence-transformers not installed.\n"
            "Install with: pip install sentence-transformers"
        )
        return
    
    # Initialize correlator
    correlator = SemanticCorrelator()
    
    if not correlator.model:
        print("Error: Could not initialize model")
        return
    
    # Load all annotations
    runbook_dir = Path(args.runbooks_dir)
    count = correlator.load_runbook_annotations(runbook_dir)
    
    if count == 0:
        print(f"No annotations found in {runbook_dir}")
        return
    
    if args.query:
        # Create query embedding
        query_emb = correlator.embed_incident(
            incident_id="query",
            cause=args.query,
            fix="",
            service="query"
        )
        
        if not query_emb:
            print("Error creating query embedding")
            return
        
        # Find similar
        similar = correlator.find_similar_incidents(
            query_emb,
            threshold=args.threshold
        )
        
        print(f"\nFound {len(similar)} similar incidents:\n")
        for incident, score in similar:
            print(f"  [{score:.2f}] {incident.service}:{incident.incident_id}")
            print(f"      Cause: {incident.cause}")
            print(f"      Fix: {incident.fix}")
            print()


if __name__ == "__main__":
    main()

"""
DatamartBundler for DTL v2.1.0

Creates and maintains NotebookLM-ready datamart bundles.

Bundle structure:
    data/datamarts/{topic_id}/
    ├── manifest.json       # Bundle metadata with fingerprint
    ├── synthesis.md        # Auto-generated topic summary (optional)
    └── sources/
        ├── {content_id}.md # Markdown export of each content item
        └── ...

Key design:
- Deterministic fingerprints from sorted source IDs
- Topic evolution via version increments
- Immutable source files (no in-place edits)
"""

import json
import hashlib
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Iterator


@dataclass
class DatamartSource:
    """A source within a datamart bundle."""
    content_id: str
    url: str
    title: str
    added_at: str
    relevance_score: float
    summary: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "url": self.url,
            "title": self.title,
            "added_at": self.added_at,
            "relevance_score": self.relevance_score,
            "summary": self.summary,
            "categories": self.categories,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DatamartSource":
        return cls(**data)


@dataclass
class DatamartManifest:
    """Manifest metadata for a datamart bundle."""
    bundle_id: str
    topic_id: str
    topic_name: str
    version: int
    created_at: str
    updated_at: str
    fingerprint: str
    source_count: int
    sources: list[DatamartSource]
    parent_topic_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    status: str = "active"  # active, archived
    
    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fingerprint": self.fingerprint,
            "source_count": self.source_count,
            "sources": [s.to_dict() for s in self.sources],
            "parent_topic_id": self.parent_topic_id,
            "tags": self.tags,
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DatamartManifest":
        sources = [DatamartSource.from_dict(s) for s in data.get("sources", [])]
        return cls(
            bundle_id=data["bundle_id"],
            topic_id=data["topic_id"],
            topic_name=data["topic_name"],
            version=data["version"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            fingerprint=data["fingerprint"],
            source_count=data["source_count"],
            sources=sources,
            parent_topic_id=data.get("parent_topic_id"),
            tags=data.get("tags", []),
            status=data.get("status", "active"),
        )


def compute_bundle_fingerprint(topic_id: str, version: int, source_ids: list[str]) -> str:
    """
    Compute deterministic fingerprint for a bundle.
    
    Fingerprint = hash of topic_id + version + sorted source IDs.
    """
    sorted_ids = sorted(source_ids)
    payload = f"{topic_id}:v{version}:" + ",".join(sorted_ids)
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


class DatamartBundler:
    """
    Creates and manages NotebookLM-ready datamart bundles.
    
    Bundles are topic-keyed folders containing:
    - manifest.json: Bundle metadata with versioning and fingerprint
    - sources/: Markdown files for each content item
    - synthesis.md: Optional auto-generated summary
    """
    
    DEFAULT_PATH = Path("data/datamarts")
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or self.DEFAULT_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_bundle_path(self, topic_id: str) -> Path:
        """Get path to a topic's bundle directory."""
        return self.base_path / topic_id
    
    def bundle_exists(self, topic_id: str) -> bool:
        """Check if a bundle exists for a topic."""
        manifest_path = self.get_bundle_path(topic_id) / "manifest.json"
        return manifest_path.exists()
    
    def read_manifest(self, topic_id: str) -> Optional[DatamartManifest]:
        """Read manifest for a topic."""
        manifest_path = self.get_bundle_path(topic_id) / "manifest.json"
        if not manifest_path.exists():
            return None
        
        with open(manifest_path) as f:
            data = json.load(f)
        
        return DatamartManifest.from_dict(data)
    
    def create_bundle(
        self,
        topic_id: str,
        topic_name: str,
        tags: list[str] = None,
        parent_topic_id: str = None,
    ) -> DatamartManifest:
        """
        Create a new empty bundle for a topic.
        
        Returns:
            The created manifest (version 1, no sources)
        """
        bundle_path = self.get_bundle_path(topic_id)
        bundle_path.mkdir(parents=True, exist_ok=True)
        (bundle_path / "sources").mkdir(exist_ok=True)
        
        now = datetime.now(timezone.utc).isoformat()
        
        manifest = DatamartManifest(
            bundle_id=f"BUNDLE-{topic_id}-v1",
            topic_id=topic_id,
            topic_name=topic_name,
            version=1,
            created_at=now,
            updated_at=now,
            fingerprint=compute_bundle_fingerprint(topic_id, 1, []),
            source_count=0,
            sources=[],
            parent_topic_id=parent_topic_id,
            tags=tags or [],
            status="active",
        )
        
        self._write_manifest(manifest)
        return manifest
    
    def add_source(
        self,
        topic_id: str,
        content_id: str,
        url: str,
        title: str,
        relevance_score: float,
        summary: str = None,
        categories: list[str] = None,
        raw_content: str = None,
    ) -> DatamartManifest:
        """
        Add a source to an existing bundle.
        
        Increments version, updates fingerprint, creates source markdown file.
        
        Args:
            topic_id: Target topic ID
            content_id: Content entry ID
            url: Source URL
            title: Content title
            relevance_score: Relevance score
            summary: Content summary
            categories: Content categories
            raw_content: Full content text for markdown file
        
        Returns:
            Updated manifest
        """
        manifest = self.read_manifest(topic_id)
        if not manifest:
            raise ValueError(f"Bundle not found: {topic_id}")
        
        if manifest.status == "archived":
            raise ValueError(f"Cannot add to archived bundle: {topic_id}")
        
        # Check for duplicate
        if any(s.content_id == content_id for s in manifest.sources):
            return manifest  # Already exists, no-op
        
        # Create source entry
        now = datetime.now(timezone.utc).isoformat()
        source = DatamartSource(
            content_id=content_id,
            url=url,
            title=title,
            added_at=now,
            relevance_score=relevance_score,
            summary=summary,
            categories=categories or [],
        )
        
        # Write source markdown file
        self._write_source_file(topic_id, source, raw_content)
        
        # Update manifest
        manifest.sources.append(source)
        manifest.source_count = len(manifest.sources)
        manifest.version += 1
        manifest.updated_at = now
        manifest.bundle_id = f"BUNDLE-{topic_id}-v{manifest.version}"
        manifest.fingerprint = compute_bundle_fingerprint(
            topic_id,
            manifest.version,
            [s.content_id for s in manifest.sources]
        )
        
        self._write_manifest(manifest)
        return manifest
    
    def remove_source(self, topic_id: str, content_id: str) -> DatamartManifest:
        """
        Remove a source from a bundle.
        
        Increments version, updates fingerprint, removes source file.
        """
        manifest = self.read_manifest(topic_id)
        if not manifest:
            raise ValueError(f"Bundle not found: {topic_id}")
        
        # Find and remove source
        manifest.sources = [s for s in manifest.sources if s.content_id != content_id]
        
        # Remove source file
        source_path = self.get_bundle_path(topic_id) / "sources" / f"{content_id}.md"
        if source_path.exists():
            source_path.unlink()
        
        # Update manifest
        now = datetime.now(timezone.utc).isoformat()
        manifest.source_count = len(manifest.sources)
        manifest.version += 1
        manifest.updated_at = now
        manifest.bundle_id = f"BUNDLE-{topic_id}-v{manifest.version}"
        manifest.fingerprint = compute_bundle_fingerprint(
            topic_id,
            manifest.version,
            [s.content_id for s in manifest.sources]
        )
        
        self._write_manifest(manifest)
        return manifest
    
    def archive_bundle(self, topic_id: str) -> DatamartManifest:
        """Archive a bundle (no new sources allowed)."""
        manifest = self.read_manifest(topic_id)
        if not manifest:
            raise ValueError(f"Bundle not found: {topic_id}")
        
        manifest.status = "archived"
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        
        self._write_manifest(manifest)
        return manifest
    
    def fork_bundle(
        self,
        parent_topic_id: str,
        new_topic_id: str,
        new_topic_name: str,
        filter_content_ids: list[str] = None,
    ) -> DatamartManifest:
        """
        Fork a bundle into a new topic.
        
        Copies selected sources to new bundle with parent reference.
        
        Args:
            parent_topic_id: Source topic to fork from
            new_topic_id: New topic ID
            new_topic_name: Display name for new topic
            filter_content_ids: Optional list of content IDs to include
                              (if None, includes all sources)
        """
        parent = self.read_manifest(parent_topic_id)
        if not parent:
            raise ValueError(f"Parent bundle not found: {parent_topic_id}")
        
        # Create new bundle
        new_manifest = self.create_bundle(
            topic_id=new_topic_id,
            topic_name=new_topic_name,
            tags=parent.tags,
            parent_topic_id=parent_topic_id,
        )
        
        # Copy sources
        for source in parent.sources:
            if filter_content_ids is None or source.content_id in filter_content_ids:
                # Copy source file
                src_file = self.get_bundle_path(parent_topic_id) / "sources" / f"{source.content_id}.md"
                dst_file = self.get_bundle_path(new_topic_id) / "sources" / f"{source.content_id}.md"
                
                if src_file.exists():
                    shutil.copy2(src_file, dst_file)
                
                new_manifest.sources.append(source)
        
        # Update manifest
        new_manifest.source_count = len(new_manifest.sources)
        new_manifest.fingerprint = compute_bundle_fingerprint(
            new_topic_id,
            new_manifest.version,
            [s.content_id for s in new_manifest.sources]
        )
        
        self._write_manifest(new_manifest)
        return new_manifest
    
    def list_bundles(self, include_archived: bool = False) -> list[DatamartManifest]:
        """List all bundles."""
        bundles = []
        
        for topic_dir in self.base_path.iterdir():
            if topic_dir.is_dir():
                manifest = self.read_manifest(topic_dir.name)
                if manifest:
                    if include_archived or manifest.status == "active":
                        bundles.append(manifest)
        
        return bundles
    
    def get_sync_summary(self, topic_id: str) -> dict:
        """
        Get summary for sync operation (dry-run preview).
        
        Returns dict with bundle info and file list.
        """
        manifest = self.read_manifest(topic_id)
        if not manifest:
            return {"error": f"Bundle not found: {topic_id}"}
        
        bundle_path = self.get_bundle_path(topic_id)
        sources_path = bundle_path / "sources"
        
        files = ["manifest.json"]
        if (bundle_path / "synthesis.md").exists():
            files.append("synthesis.md")
        
        if sources_path.exists():
            for f in sources_path.iterdir():
                if f.suffix == ".md":
                    files.append(f"sources/{f.name}")
        
        return {
            "topic_id": topic_id,
            "topic_name": manifest.topic_name,
            "version": manifest.version,
            "fingerprint": manifest.fingerprint,
            "source_count": manifest.source_count,
            "files": files,
            "bundle_path": str(bundle_path),
            "status": manifest.status,
        }
    
    def _write_manifest(self, manifest: DatamartManifest):
        """Write manifest to file."""
        manifest_path = self.get_bundle_path(manifest.topic_id) / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest.to_dict(), f, indent=2)
    
    def _write_source_file(
        self,
        topic_id: str,
        source: DatamartSource,
        raw_content: str = None,
    ):
        """Write source markdown file."""
        sources_path = self.get_bundle_path(topic_id) / "sources"
        sources_path.mkdir(exist_ok=True)
        
        source_file = sources_path / f"{source.content_id}.md"
        
        # Build markdown content
        lines = [
            f"# {source.title}",
            "",
            f"**Source:** {source.url}",
            f"**Added:** {source.added_at}",
            f"**Relevance:** {source.relevance_score:.2f}",
        ]
        
        if source.categories:
            lines.append(f"**Categories:** {', '.join(source.categories)}")
        
        lines.append("")
        
        if source.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(source.summary)
            lines.append("")
        
        if raw_content:
            lines.append("## Content")
            lines.append("")
            lines.append(raw_content)
        
        with open(source_file, "w") as f:
            f.write("\n".join(lines))

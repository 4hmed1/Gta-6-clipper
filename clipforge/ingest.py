# Ingest Module
# Handles video and audio ingestion, validation, and downloading

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from clipforge.security import validate_url, sanitize_filename, validate_file_size
from clipforge.resilience import ResilienceEngine

from clipforge.ingest.downloader import YTDLPDownloader
from clipforge.ingest.heatmap import HeatmapAnalyzer
from clipforge.ingest.captions import CaptionExtractor


class IngestError(Exception):
    """Exception raised for ingest errors."""
    pass


class VideoIngest:
    """Handles video ingestion and preparation for processing."""

    def __init__(self, resilience_engine: ResilienceEngine):
        self.downloader = YTDLPDownloader()
        self.heatmap_analyzer = HeatmapAnalyzer()
        self.caption_extractor = CaptionExtractor()
        self.resilience_engine = resilience_engine

    def ingest_video(self, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest video from URL with validation and preprocessing.

        Args:
            url: YouTube video URL
            options: Processing options

        Returns:
            Ingested video data with metadata

        Raises:
            IngestError: If ingestion fails
        """
        # Validate URL
        validated_url = validate_url(url)

        # Create project directory
        project_id = hashlib.sha256(validated_url.encode()).hexdigest()[:16]
        project_dir = Path(f"projects/{project_id}")
        project_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Download video metadata and info
            metadata = self.downloader.get_metadata(validated_url)
            metadata["project_id"] = project_id
            metadata["ingested_at"] = int(time.time())

            # Save metadata
            metadata_file = project_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Download and analyze heatmap if available
            if metadata.get("heatmap_available"):
                heatmap_path = project_dir / "heatmap.json"
                heatmap_data = self.heatmap_analyzer.process_video(
                    validated_url,
                    metadata["duration"]
                )

                with open(heatmap_path, 'w') as f:
                    json.dump(heatmap_data, f, indent=2)

                metadata["heatmap_path"] = str(heatmap_path)

            # Extract captions
            captions = self.caption_extractor.process_video(validated_url)

            metadata["captions_path"] = str(project_dir / "captions.json")
            with open(metadata["captions_path"], 'w') as f:
                json.dump(captions, f, indent=2)

            # Process sections if specified
            sections = self._process_sections(
                validated_url,
                options.get("time_range"),
                project_dir
            )

            return {
                "project_id": project_id,
                "metadata": metadata,
                "sections": sections,
                "status": "completed"
            }

        except Exception as e:
            raise IngestError(f"Video ingestion failed: {str(e)}")

    def _process_sections(
        self,
        url: str,
        time_range: Optional[Tuple[float, float]],
        project_dir: Path
    ) -> List[Dict[str, Any]]:
        """
        Process video sections for efficient processing.

        Args:
            url: Video URL
            time_range: Time range to process
            project_dir: Project directory

        Returns:
            List of processed sections
        """
        sections = []

        if time_range:
            start_time, end_time = time_range

            # Create section directory
            section_dir = project_dir / "sections"
            section_dir.mkdir(exist_ok=True)

            # Download only specified section
            section_path = section_dir / "section.mp4"
            self.downloader.download_section(
                url,
                start_time,
                end_time,
                str(section_path)
            )

            sections.append({
                "start": start_time,
                "end": end_time,
                "path": str(section_path),
                "duration": end_time - start_time
            })

        else:
            # Process entire video
            sections.append({
                "start": 0,
                "end": None,  # Entire video
                "path": None,  # Will download full video
                "duration": None
            })

        return sections
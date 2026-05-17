from enum import Enum
from pandas import DataFrame
from app.etl.data.base_data_types import IExtractor, FieldPathBase
from app.etl.data.remote.gee.google_earth_api_data_collector import (
    GoogleEarthAPIDataCollector,
)
import re


class RemoteDataTypes(Enum):
    """Remote Types"""

    GEE = "gee"


class GEEDataExtractor(FieldPathBase, IExtractor):
    def __init__(self, path: str):
        FieldPathBase.__init__(self, path)

    def _parse_path(self, path: str):
        path = path.strip()

        # remove optional wrapper {}
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]

        # Split by pipe: project|dataset|start|end|lon|lat|scale
        parts = path.split("|")

        if len(parts) < 7:
            raise ValueError(
                f"Expected at least 7 parts "
                f"(project|dataset|start|end|lon|lat|scale), "
                f"got {len(parts)}: {parts}"
            )

        project = parts[0]
        dataset_block = parts[1]
        start = parts[2]
        end = parts[3]
        lon = parts[4]
        lat = parts[5]
        scale = parts[6]

        # Support multiple datasets:
        # [dataset1,dataset2,dataset3]
        if dataset_block.startswith("[") and dataset_block.endswith("]"):
            datasets = [
                d.strip()
                for d in dataset_block[1:-1].split(",")
                if d.strip()
            ]
        else:
            datasets = [dataset_block.strip()]

        return project, datasets, start, end, lon, lat, scale

    def extract(self) -> DataFrame:
        full_path = self.path.strip()

        # ---------------------------------------------------
        # AREA((lon,lat),(lon,lat),...)
        # ---------------------------------------------------
        area_match = re.search(r"AREA\(\((.+)\)\)", full_path)

        if area_match:
            # Extract everything before AREA(...)
            before_area = full_path[: area_match.start()].strip("|")

            (
                project,
                datasets,
                start,
                end,
                _,
                _,
                _,
            ) = self._parse_path(before_area)

            collector = GoogleEarthAPIDataCollector(projectname=project)

            # Parse polygon coordinates
            coord_str = area_match.group(1)

            pairs = re.findall(
                r"([\d.+-]+)\s*,\s*([\d.+-]+)",
                coord_str,
            )

            coords = [
                [float(lon), float(lat)]
                for lon, lat in pairs
            ]

            dfs = []

            for dataset in datasets:
                df = collector.collect_area(
                    dataset=dataset,
                    start_date=start,
                    end_date=end,
                    coordinates=coords,
                )
                dfs.append(df)

            if len(dfs) == 1:
                return dfs[0]

            # Auto join multiple area datasets
            from app.etl.core import join

            result = dfs[0]

            for df in dfs[1:]:
                result = join(
                    result,
                    df,
                    "time",
                    "time",
                    how="outer",
                )

            return result

        # ---------------------------------------------------
        # NORMAL POINT EXTRACTION
        # ---------------------------------------------------
        (
            project,
            datasets,
            start,
            end,
            lon,
            lat,
            scale,
        ) = self._parse_path(full_path)

        collector = GoogleEarthAPIDataCollector(projectname=project)

        dfs = []

        for dataset in datasets:
            df = collector.collect(
                satellite=dataset,
                start_date=start,
                end_date=end,
                longitude=float(lon),
                latitude=float(lat),
                scale=float(scale),
            )

            dfs.append(df)

        # Single dataset
        if len(dfs) == 1:
            return dfs[0]

        # Auto join multiple datasets
        from app.etl.core import join

        result = dfs[0]

        for df in dfs[1:]:
            result = join(
                result,
                df,
                "time",
                "time",
                how="outer",
            )

        return result
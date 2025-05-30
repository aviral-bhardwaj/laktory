import os
import shutil
from pathlib import Path
from typing import Any
from typing import Literal
from typing import Union

from pydantic import field_validator
from pydantic import model_validator

from laktory._logger import get_logger
from laktory.models.datasinks.basedatasink import BaseDataSink
from laktory.models.datasources.filedatasource import FileDataSource
from laktory.polars import PolarsDataFrame
from laktory.polars import PolarsLazyFrame
from laktory.spark import SparkDataFrame

logger = get_logger(__name__)


class FileDataSink(BaseDataSink):
    """
    Disk file(s) data sink such as csv, parquet or Delta Table.

    Attributes
    ----------
    checkpoint_location:
        Path to which the checkpoint file for streaming dataframe should
        be written. If `None`, parent directory of `path` is used.
    format:
        Format of the data files
    path:
        Path to which the DataFrame needs to be written.

    Examples
    ---------
    ```python
    import pandas as pd

    from laktory import models

    df = spark.createDataFrame(
        pd.DataFrame(
            {
                "symbol": ["AAPL", "GOOGL"],
                "price": [200.0, 205.0],
                "tstamp": ["2023-09-01", "2023-09-01"],
            }
        )
    )

    sink = models.FileDataSink(
        path="/Volumes/sources/landing/events/yahoo-finance/stock_price",
        format="PARQUET",
        mode="OVERWRITE",
    )
    # sink.write(df)

    # Sink with Change Data Capture processing
    sink = models.FileDataSink(
        path="/Volumes/sources/landing/events/yahoo-finance/stock_price",
        format="DELTA",
        mode="MERGE",
        merge_cdc_options={
            "scd_type": 1,
            "primary_keys": ["symbol", "tstamp"],
        },
    )
    # sink.write(df)
    ```
    """

    checkpoint_location: Union[str, None] = None
    format: Literal["CSV", "PARQUET", "DELTA", "JSON", "EXCEL"] = "DELTA"
    path: str

    @field_validator("path", mode="before")
    @classmethod
    def posixpath_to_string(cls, value: Any) -> Any:
        if isinstance(value, Path):
            value = str(value)
        return value

    @model_validator(mode="after")
    def merge_and_format(self) -> Any:
        if self.mode == "MERGE":
            if self.format.lower() not in ["delta"]:
                raise ValueError(
                    "Merge write mode is only supported for 'DELTA' `format`"
                )

        return self

    # ----------------------------------------------------------------------- #
    # Properties                                                              #
    # ----------------------------------------------------------------------- #

    @property
    def _id(self):
        return str(self.path)

    # ----------------------------------------------------------------------- #
    # Methods                                                                 #
    # ----------------------------------------------------------------------- #

    def _write_spark(self, df: SparkDataFrame, mode=None, full_refresh=False) -> None:
        if self.format in ["EXCEL"]:
            raise ValueError(f"'{self.format}' format is not supported with Spark")

        # Set mode
        if mode is None:
            mode = self.mode

        if mode.lower() == "merge":
            self.merge_cdc_options.execute(source=df)
            return

        # Full Refresh
        if full_refresh or not self.exists(spark=df.sparkSession):
            if df.isStreaming:
                pass
                # .is_aggregate() method seems unreliable. Disabling for now.
                # if df.laktory.is_aggregate():
                #     logger.info(
                #         "Full refresh or initial load. Switching to COMPLETE mode."
                #     )
                #     mode = "COMPLETE"
            else:
                logger.info(
                    "Full refresh or initial load. Switching to OVERWRITE mode."
                )
                mode = "OVERWRITE"

        # Default Options
        _options = {"mergeSchema": "true", "overwriteSchema": "false"}
        if mode in ["OVERWRITE", "COMPLETE"]:
            _options["mergeSchema"] = "false"
            _options["overwriteSchema"] = "true"
        if df.isStreaming:
            _options["checkpointLocation"] = self._checkpoint_location

        # User Options
        for k, v in self.write_options.items():
            _options[k] = v

        if df.isStreaming:
            logger.info(
                f"Writing df as stream {self.format} to {self.path} with mode {mode} and options {_options}"
            )
            writer = (
                df.writeStream.format(self.format.lower())
                .outputMode(mode)
                .trigger(availableNow=True)  # TODO: Add option for trigger?
                .options(**_options)
            )
            if self.cluster_by:
                writer = writer.clusterBy(*self.cluster_by)
            query = writer.start(self.path)
            query.awaitTermination()

        else:
            logger.info(
                f"Writing df as static {self.format} to {self.path} with mode {mode} and options {_options}"
            )
            writer = df.write.mode(mode).format(self.format.lower()).options(**_options)
            if self.cluster_by:
                writer = writer.clusterBy(*self.cluster_by)
            writer.save(self.path)

    def _write_polars(self, df: PolarsDataFrame, mode=None, full_refresh=False) -> None:
        isStreaming = False

        if self.format != "DELTA":
            if mode:
                raise ValueError(
                    "'mode' configuration with Polars only supported by 'DELTA' format"
                )
        else:
            if full_refresh or not self.exists():
                mode = "OVERWRITE"

            if not mode:
                raise ValueError(
                    "'mode' configuration required with Polars 'DELTA' format"
                )

        if isStreaming:
            logger.info(
                f"Writing df as stream {self.format} to {self.path} with mode {mode}"
            )

        else:
            logger.info(
                f"Writing df as static {self.format} to {self.path} with mode {mode}"
            )

        if isinstance(df, PolarsLazyFrame):
            df = df.collect()

        if self.format.lower() == "csv":
            df.write_csv(self.path, **self.write_options)
        elif self.format.lower() == "delta":
            df.write_delta(self.path, mode=mode, **self.write_options)
        elif self.format.lower() == "excel":
            df.write_excel(self.path, **self.write_options)
        elif self.format.lower() == "json":
            df.write_json(self.path, **self.write_options)
        elif self.format.lower() == "parquet":
            df.write_parquet(self.path, **self.write_options)

    # ----------------------------------------------------------------------- #
    # Purge                                                                   #
    # ----------------------------------------------------------------------- #

    def purge(self, spark=None):
        """
        Delete sink data and checkpoints
        """
        # TODO: Now that sink switch to overwrite when sink does not exists or when
        # a full refresh is requested, the purge method should not delete the data
        # by default, but only the checkpoints. Also consider truncating the table
        # instead of dropping it.

        # Remove Data
        if os.path.exists(self.path):
            is_dir = os.path.isdir(self.path)
            if is_dir:
                logger.info(f"Deleting data dir {self.path}")
                shutil.rmtree(self.path)
            else:
                logger.info(f"Deleting data file {self.path}")
                os.remove(self.path)

        # TODO: Add support for Databricks dbfs / workspace / Volume?

        # Remove Checkpoint
        self._purge_checkpoint(spark=spark)

    # ----------------------------------------------------------------------- #
    # Source                                                                  #
    # ----------------------------------------------------------------------- #

    def as_source(self, as_stream: bool = None) -> FileDataSource:
        """
        Generate a file data source with the same path as the sink.

        Parameters
        ----------
        as_stream:
            If `True`, sink will be read as stream.

        Returns
        -------
        :
            File Data Source
        """

        source = FileDataSource(
            path=self.path,
            format=self.format,
        )

        if as_stream:
            source.as_stream = as_stream

        if self.dataframe_backend:
            source.dataframe_backend = self.dataframe_backend
        source.parent = self.parent

        return source

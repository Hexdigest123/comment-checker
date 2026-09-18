import pandas as pd
from typing import Optional, Dict


class CSVReader:
    """Reader for CSV files with support for multiple formats.
    
    This reader can handle both the internal CSV format and ExportComments
    CSV exports, with automatic column mapping.
    """

    def __init__(
        self, 
        file_path: str, 
        delimiter: str = ",", 
        encoding: str = "utf-8",
        auto_map: bool = True,
    ) -> None:
        """Initialize the CSVReader for further processing.

        Args:
            file_path: The full absolute path to the input file.
            delimiter: The CSV delimiter. Default: comma.
            encoding: The file encoding. Default: utf-8.
            auto_map: Whether to automatically map ExportComments columns to internal format.
        """
        self.file_path = file_path
        self.delimiter = delimiter
        self.encoding = encoding
        self.auto_map = auto_map

        self.df = self.__to_dataframe()
        
        # Auto-map columns if requested
        if auto_map:
            self.df = self._map_columns()

    def __to_dataframe(self) -> pd.DataFrame:
        """Read the CSV file into a DataFrame."""
        return pd.read_csv(
            self.file_path,
            sep=self.delimiter,
            encoding=self.encoding,
            header=0,
            na_values=["NA", "N/A", "", "null", "None"],
            on_bad_lines="warn",
        )

    def _map_columns(self) -> pd.DataFrame:
        """Map ExportComments columns to internal format if needed.
        
        Returns:
            DataFrame with mapped columns.
        """
        return self.df

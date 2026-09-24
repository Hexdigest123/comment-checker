import pandas as pd


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
        # Check if this looks like an ExportComments export
        exportcomments_indicators = ['text', 'username', 'author', 'timestamp', 'comment']
        
        if any(col.lower() in self.df.columns for col in exportcomments_indicators):
            return self._map_exportcomments_to_internal()
        
        return self.df

    def _map_exportcomments_to_internal(self) -> pd.DataFrame:
        """Map ExportComments CSV columns to internal format.

        Returns:
            DataFrame with columns mapped to internal format.
        """
        column_mapping = {
            "text": "Comment",
            "comment": "Comment",
            "comment_text": "Comment",
            "body": "Comment",
            "content": "Comment",
            "username": "Username",
            "author": "Username",
            "user": "Username",
            "name": "Name",
            "display_name": "Name",
            "timestamp": "Date",
            "created_at": "Date",
            "date": "Date",
            "published": "Date",
            "time": "Date",
            "likes": "Likes",
            "like_count": "Likes",
            "replies": "Replies",
            "reply_count": "Replies",
            "profile_url": "Profile URL",
            "user_url": "Profile URL",
            "url": "Comment URL",
            "permalink": "Comment URL",
            "comment_url": "Comment URL",
            "user_id": "Profile ID",
            "author_id": "Profile ID",
            "id": "Comment ID",
            "comment_id": "Comment ID",
            "avatar": "Thumbnail",
            "thumbnail": "Thumbnail",
            "image": "Thumbnail",
            "priority": "Priorit\u00e4t",
            "Priority": "Priorit\u00e4t",
            "category": "Kategorie",
            "Category": "Kategorie",
        }

        mapped_data = {}

        for export_col, internal_col in column_mapping.items():
            if export_col in self.df.columns:
                mapped_data[internal_col] = self.df[export_col]
            else:
                for df_col in self.df.columns:
                    if df_col.lower().strip() == export_col.lower().strip():
                        mapped_data[internal_col] = self.df[df_col]
                        break

        for col in self.df.columns:
            col_lower = col.lower().strip()
            is_mapped = any(
                col_lower == ec.lower().strip()
                for ec in column_mapping.keys()
            )
            if not is_mapped and col not in mapped_data:
                mapped_data[col] = self.df[col]

        return pd.DataFrame(mapped_data)

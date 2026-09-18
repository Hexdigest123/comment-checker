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
        # Define the mapping from ExportComments columns to internal columns
        column_mapping = {
            # Comment text
            "text": "Comment",
            "comment": "Comment",
            "comment_text": "Comment",
            "body": "Comment",
            "content": "Comment",
            
            # Username
            "username": "Username",
            "author": "Username",
            "user": "Username",
            "name": "Name",
            "display_name": "Name",
            
            # Date/Time
            "timestamp": "Date",
            "created_at": "Date",
            "date": "Date",
            "published": "Date",
            "time": "Date",
            
            # Likes
            "likes": "Likes",
            "like_count": "Likes",
            
            # Replies
            "replies": "Replies",
            "reply_count": "Replies",
            
            # Profile info
            "profile_url": "Profile URL",
            "user_url": "Profile URL",
            "url": "Comment URL",
            "permalink": "Comment URL",
            "comment_url": "Comment URL",
            
            # IDs
            "user_id": "Profile ID",
            "author_id": "Profile ID",
            "id": "Comment ID",
            "comment_id": "Comment ID",
            
            # Media
            "avatar": "Thumbnail",
            "thumbnail": "Thumbnail",
            "image": "Thumbnail",
            
            # Priority (internal)
            "priority": "Priorit\u00e4t",
            "Priority": "Priorit\u00e4t",
            
            # Category (internal)
            "category": "Kategorie",
            "Category": "Kategorie",
        }
        
        # Create a new DataFrame with mapped columns
        mapped_data = {}
        
        # First, map internal columns from ExportComments columns
        for export_col, internal_col in column_mapping.items():
            # Try exact match
            if export_col in self.df.columns:
                mapped_data[internal_col] = self.df[export_col]
            else:
                # Try case-insensitive match
                for df_col in self.df.columns:
                    if df_col.lower().strip() == export_col.lower().strip():
                        mapped_data[internal_col] = self.df[df_col]
                        break
        
        # Add any additional columns from the original that don't map
        for col in self.df.columns:
            col_lower = col.lower().strip()
            # Skip if this column maps to an internal column we already have
            is_mapped = any(
                col_lower == ec.lower().strip() 
                for ec in column_mapping.keys()
            )
            if not is_mapped and col not in mapped_data:
                mapped_data[col] = self.df[col]
        
        return pd.DataFrame(mapped_data)

    def get_column_mapping(self) -> Dict[str, str]:
        """Get the column mapping that was applied.
        
        Returns:
            Dictionary mapping internal column names to original column names.
        """
        # This would need to be tracked during initialization
        # For now, return an empty dict
        return {}

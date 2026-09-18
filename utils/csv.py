import pandas as pd


class CSVReader:

    def __init__(
        self, file_path: str, delimiter: str = ",", encoding: str = "utf-8"
    ) -> None:
        """initialize the CSVReader for further processing

        Args:
            file_path: requires the full absolute path to the input file
        """
        self.file_path = file_path
        self.delimiter = delimiter
        self.encoding = encoding

        self.df = self.__to_dataframe()

    def __to_dataframe(self) -> pd.DataFrame:
        return pd.read_csv(
            self.file_path,
            sep=self.delimiter,
            encoding=self.encoding,
            header=0,
            na_values=["NA"],
        )

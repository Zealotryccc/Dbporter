import pandas as pd

from dbporter.formats.csv_format import read_csv, write_csv
from dbporter.formats.json_format import read_json, write_json


def test_csv_roundtrip(tmp_path):
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    path = tmp_path / "data.csv"
    
    write_csv(df, path)
    df_back = read_csv(path)
    
    assert df.equals(df_back)


def test_json_roundtrip(tmp_path):
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    path = tmp_path / "data.json"
    
    write_json(df, path)
    df_back = read_json(path)
    
    assert df.equals(df_back)
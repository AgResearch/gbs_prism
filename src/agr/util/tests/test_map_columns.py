from agr.util import map_columns


def test_map_columns():
    in_headings = ["a", "b", "c", "d", "e"]
    in_rows = [[1, 2, 3, 4, 5], [11, 12, 13, 14, 15], [21, 22, 23, 24, 25]]
    out_headings = ["c", "b"]
    out_rows = list(map_columns(in_headings, out_headings, iter(in_rows)))
    assert out_rows == [[3, 2], [13, 12], [23, 22]]

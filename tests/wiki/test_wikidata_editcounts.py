from unittest.mock import MagicMock

from src.wiki.client import WikiClient


def test_get_editcounts_empty():
    res = WikiClient({}).get_editcounts([])
    assert res == {}


def test_get_editcounts_mocked_site():
    mock_site = MagicMock()
    mock_site.get.return_value = {
        "query": {
            "users": [
                {"name": "UserA", "editcount": 1500},
                {"name": "UserB", "editcount": 42},
            ]
        }
    }

    users = ["UserA", "UserB"]
    res = WikiClient(mock_site).get_editcounts(users)

    assert res == {"UserA": 1500, "UserB": 42}
    mock_site.get.assert_called_once_with(
        "query",
        list="users",
        usprop="editcount",
        ususers="UserA|UserB",
        formatversion=2,
        format="json",
    )


def test_get_editcounts_batching():
    mock_site = MagicMock()
    # Batch size is 50. Provide 55 users.
    users = [f"User{i}" for i in range(55)]

    def side_effect(action, **kwargs):
        ususers = kwargs.get("ususers", "").split("|")
        return {"query": {"users": [{"name": u, "editcount": 10} for u in ususers]}}

    mock_site.get.side_effect = side_effect

    res = WikiClient(mock_site).get_editcounts(users)
    assert len(res) == 55
    assert res["User0"] == 10
    assert res["User54"] == 10
    assert mock_site.get.call_count == 2

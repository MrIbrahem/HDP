# last_edit_timestamp

## meta wiki API

```json
{
    "action": "query",
    "format": "json",
    "list": "globalcontributions",
    "utf8": 1,
    "formatversion": "2",
    "guctarget": "Mr. Ibrahem",
    "guclimit": "1"
}
```

Result: (116 ms)

```json
{
    "batchcomplete": true,
    "continue": {
        "gucoffset": "20261002001304|0|31116293",
        "continue": "-||"
    },
    "query": {
        "globalcontributions": {
            "entries": [
                {
                    "wikiid": "metawiki",
                    "revid": "31116293",
                    "timestamp": "20261002001304"
                },
                {
                    "wikiid": "arwiki",
                    "revid": "76823306",
                    "timestamp": "20261001061625"
                }
            ]
        }
    }
}
```

## Xtools

```url
https://xtools.wmcloud.org/api/user/globalcontribs/Mr.%20Ibrahem/all?limit=2
```

Result: (6.145 s)

```json
{
    "username": "Mr. Ibrahem",
    "namespace": "all",
    "limit": 2,
    "project": "meta.wikimedia.org",
    "globalcontribs": [
        {
            "full_page_title": "User:Mr. Ibrahem/hdp",
            "page_title": "Mr. Ibrahem/hdp",
            "namespace": 2,
            "project": "meta.wikimedia.org",
            "username": "Mr. Ibrahem",
            "rev_id": 31116293,
            "timestamp": "2026-10-02T00:13:04Z",
            "minor": false,
            "length": 71563,
            "length_change": -27,
            "comment": ""
        },
        {
            "full_page_title": "User talk:Mr. Ibrahem",
            "page_title": "Mr. Ibrahem",
            "namespace": 3,
            "project": "ar.wikipedia.org",
            "username": "Mr. Ibrahem",
            "rev_id": 76823306,
            "timestamp": "2026-10-01T06:16:25Z",
            "minor": false,
            "length": 3179,
            "length_change": 285,
            "comment": "/* مسابقة ويكي مصر 2026 */ ردّ"
        }
    ],
    "continue": "2026-10-01T06:16:25Z",
    "elapsed_time": 6.145
}
```

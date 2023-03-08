# scammer
scammer provide a way to reschema your dict

## examples
```py
from scammer import reschema_dict, reschema_list


data = {
    "id": 123,
    "name": "Foo",
    "friends": [
        {"name": "Oof"}
    ],
}

reschemed_data = reschema_dict(data, {
    "id": "/id",
    "person_name": "/name",
    "people": reschema_list("/friends", {
        "man_name": "./name",
        "friend": "../name",
    })
})
```

output:
```py
{
    'id': 123,
    'people': [{'friend': 'Foo', 'man_name': 'Oof'}],
    'person_name': 'Foo'
}
```


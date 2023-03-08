from __future__ import annotations
from random import randint
from pprint import pprint
from typing import (
    Union, 
    Dict, 
    Any, 
    List, 
    Tuple, 
    Optional
)


class SchemaPathError(Exception):
    def __init__(self, message: str, path: str) -> None:
        super().__init__(
            f'{message} ({path})'
        )


class _Undefined():
    """
    a type that helps to distingush between if the found key is None, 
    or if the key doesn't even exists
    """


undefined = _Undefined()


class _SchemaData:

    __slots__ = ['_data']
    
    def __init__(
        self, 
        data: Dict[Any, Any]
    ) -> None:
        if not isinstance(data, dict):
            raise ValueError(
                f"schema data, should only be of type dict and not {type(data)}"
            )
        self._data = data

    def get(self, path: str) -> Any:
        fields = path.strip('/').split('/')
        value = self._data

        for field in fields:
            if field not in value:
                return undefined
            value = value[field]
        return value


class _ReSchemaBase:

    __slots__ = [
        '_schema_data',
        '_schema_template',
        '_add_empty_dict',
        '_add_empty_lists',
        '_add_missing_keys',
        '_raise_missing_keys',
        '_as_child',
        '_parent',
        '_schema_path',
    ]
    
    def __init__(
        self, 
        schema_data: Union[Dict[Any, Any], List[Any], _SchemaData],
        schema_template: Dict[str, Any],
        *,
        add_empty_dict,
        add_empty_lists,
        add_missing_keys,
        raise_missing_keys,
    ) -> None:
        if isinstance(schema_data, dict):
            schema_data = _SchemaData(schema_data)

        self._schema_data = schema_data
        self._schema_template = schema_template

        self._add_empty_dict = add_empty_dict
        self._add_empty_lists = add_empty_lists
        self._add_missing_keys = add_missing_keys
        self._raise_missing_keys = raise_missing_keys

        # if schema data is `str` it means
        # its a path, a path to data we take from the parent
        self._as_child = isinstance(schema_data, str)
        self._parent = None 

        if self._as_child:
            self._schema_path = schema_data
        else:
            self._schema_path = None 

    @property
    def schema_data(self) -> _SchemaData:
        return self._schema_data

    @property
    def schema_template(self) -> Dict[str, Any]:
        return self._schema_template

    def get(
        self, 
        path: str, 
        *, 
        required: bool = False, 
        _child: Optional[_ReSchemaBase] = None
    ) -> Any:
        if (
            (path.startswith('/') or path.startswith('../')) and 
            self._parent
        ):
            # remove only a single `../` prefix
            if path.startswith('../'):
                path = path[len('../'):]
            return self._parent.get(path, required=required, _child=self)
        elif path.startswith('../'):
            raise SchemaPathError(
                'cannot retrive data from parent, because there are no more parents', path
            )

        path = path.strip('./')

        # if `self.schema_data` is not _SchemaData its probably a list, if _child is not None,
        # it means the path is requesting something from root, and we are the parent of child,
        # because `self.schema_data` is a list, we can't return the correct context, the correct context
        # is in the child `schema_data`
        if not isinstance(self.schema_data, _SchemaData):
            if self._parent:
                return self._parent.get(path, required=required, _child=_child)

            if _child is not None:
                path = path.strip('/')
                return _child.get(path, required=required)
            raise SchemaPathError("given path is broken", path)

        data = self.schema_data.get(path)

        if required and data is undefined:
            raise SchemaPathError('given path does not exists', path)
        return data

    def set_parent(self, parent: _ReSchemaBase) -> None:
        self._as_child = True 
        self._parent = parent
        
        # if the given schema data was a path, we should
        # resolve it now and get the data from the parent
        if self._schema_path:
            self._schema_data = self.get(
                f'../{self._schema_path}', required=self._raise_missing_keys
            )

    def reschema(self):
        # if we are a child and the parent is None, it means
        # we didn't not really initilized yet, we should wait for the parent
        # and only then parse
        if self._as_child and self._parent is None:
            return self 

        if self.schema_data is undefined:
            return undefined
        return self._reschema(self.schema_template)

    def _reschema(self, template):
        raise NotImplementedError()


class _ReSchemaDict(_ReSchemaBase):
    def _reschema(
        self, 
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        reschema = {}

        for k, v in template.items():
            if isinstance(v, (list, tuple, set)):
                raise ValueError('to reschema a list please use `reschema_list` instead of passing a list')

            if isinstance(v, dict):
                data = self._reschema(v)
            elif isinstance(v, _ReSchemaBase):
                v.set_parent(self)
                data = v.reschema()
            else:
                data = self.get(v, required=self._raise_missing_keys)

            if data is undefined and self._add_missing_keys:
                data = None
            elif (
                isinstance(data, (list, tuple, set)) and len(data) == 0 and
                not self._add_empty_lists or 
                isinstance(data, dict) and len(data) == 0 and
                not self._add_empty_dict
            ):
                # if current data is an empty list and we required
                # NOT to add empty lists, then make data undefined, we do
                # the same for empty dict
                data = undefined

            if data is not undefined:
                reschema[k] = data
        return reschema
            

class _ReSchemaList(_ReSchemaBase):
    def _reschema(self, template):
        reschema = []
        id = randint(1, 100)

        for o in self.schema_data:
            dict_reschemer = _ReSchemaDict(
                o, template,
                add_empty_dict=self._add_empty_dict,
                add_empty_lists=self._add_empty_lists,
                add_missing_keys=self._add_missing_keys,
                raise_missing_keys=self._raise_missing_keys
            )
            dict_reschemer.set_parent(self)
            reschemed_dict = dict_reschemer.reschema()

            if len(reschemed_dict) != 0 or self._add_empty_dict:
                reschema.append(reschemed_dict)
        return reschema
            

def reschema_dict(
    data: Dict[str, Any], 
    schema: Dict[str, Any],
    *,
    add_empty_dict=False,
    add_empty_lists=False,
    add_missing_keys=False,
    raise_missing_keys=False,
) -> Dict[str, Any]:
    return _ReSchemaDict(
        data, 
        schema, 
        add_empty_dict=add_empty_dict,
        add_empty_lists=add_empty_lists,
        add_missing_keys=add_missing_keys, 
        raise_missing_keys=raise_missing_keys
    ).reschema()


def reschema_list(
    data: List[Any], 
    schema: Dict[str, Any],
    *,
    add_empty_dict=False,
    add_empty_lists=False,
    add_missing_keys=False,
    raise_missing_keys=False,
) -> List[Dict[str, Any]]:
    return _ReSchemaList(
        data, 
        schema, 
        add_empty_dict=add_empty_dict,
        add_empty_lists=add_empty_lists,
        add_missing_keys=add_missing_keys, 
        raise_missing_keys=raise_missing_keys
    ).reschema()

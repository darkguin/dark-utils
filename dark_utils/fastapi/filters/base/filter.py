from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Extra, ValidationError, create_model, fields, validator
from pydantic.fields import FieldInfo, ModelField


class BaseFilterModel(BaseModel):
    class Config:
        extra = Extra.forbid

    class Constants:
        model: Type
        ordering_field_name: str = 'order_by'
        search_model_fields: List[str]
        search_field_name: str = 'search'
        prefix: str

    def filter(self, query):
        ...

    @property
    def filtering_fields(self):
        fields = self.dict(exclude_none=True, exclude_unset=True)
        fields.pop(self.Constants.ordering_field_name, None)
        return fields.items()

    def sort(self, query):
        ...

    @property
    def ordering_values(self):
        try:
            return getattr(self, self.Constants.ordering_field_name)
        except AttributeError:
            raise AttributeError(f'Ordering field {self.Constants.ordering_field_name} is not defined')

    @validator('*', pre=True)
    def split_str(cls, value, field):
        ...

    @validator('*', pre=True, allow_reuse=True, check_fields=False)
    def strip_order_by_values(cls, order_by_values: list[str] | Any, field: ModelField):
        if field.name != cls.Constants.ordering_field_name:
            return order_by_values

        if not order_by_values:
            return None

        stripped_values = [
            stripped for stripped in (field_name.strip() for field_name in order_by_values) if stripped
        ]
        return stripped_values

    @validator('*', allow_reuse=True, check_fields=False)
    def validate_order_by_values(cls, order_by_values: list[str] | Any, field: ModelField):
        if field.name != cls.Constants.ordering_field_name:
            return order_by_values

        if not order_by_values:
            return None

        ordering_fields = [
            field_name_direction.replace('-', '').replace('+', '') for field_name_direction in order_by_values
        ]

        invalid_ordering_fields = [
            field_name for field_name in ordering_fields if not hasattr(cls.Constants.model, field_name)
        ]
        if invalid_ordering_fields:
            raise ValueError(f"Invalid ordering fields: {', '.join(sorted(invalid_ordering_fields))}")

        fields_occurrences = Counter(ordering_fields)
        duplicated_field_names = [
            field_name for field_name, occurrences in fields_occurrences.items() if occurrences > 1
        ]
        if duplicated_field_names:
            raise ValueError(f"Duplicated ordering_fields: {', '.join(sorted(duplicated_field_names))}")

        return order_by_values


def with_prefix(new_prefix: str, Filter: Type[BaseFilterModel]):
    class NestedFilter(Filter):
        class Config:
            extra = Extra.forbid

            @classmethod
            def alias_generator(cls, string: str) -> str:
                return f'{new_prefix}__{string}'

        class Constants(Filter.Constants):
            prefix = new_prefix

    return NestedFilter


def _list_to_str_fields(Filter: Type[BaseFilterModel]):
    ret: Dict[str, Tuple[Union[object, Type], Optional[FieldInfo]]] = {}
    for f in Filter.__fields__.values():
        field_info = deepcopy(f.field_info)
        if f.shape == fields.SHAPE_LIST:
            if isinstance(field_info.default, Iterable):
                field_info.default = ','.join(field_info.default)
            ret[f.name] = (str if f.required else Optional[str], field_info)
        else:
            field_type = Filter.__annotations__.get(f.name, f.outer_type_)
            ret[f.name] = (field_type if f.required else Optional[field_type], field_info)

    return ret


def FilterDepends(Filter: Type[BaseFilterModel], *, by_alias: bool = False, use_cache: bool = True) -> Any:
    fields = _list_to_str_fields(Filter)
    GeneratedFilter: Type[BaseFilterModel] = create_model(Filter.__class__.__name__, **fields)

    class FilterWrapper(GeneratedFilter):
        def filter(self, *args, **kwargs):
            try:
                original_filter = Filter(**self.dict(by_alias=by_alias))
            except ValidationError as e:
                raise RequestValidationError(e.raw_errors) from e
            return original_filter.filter(*args, **kwargs)

        def sort(self, *args, **kwargs):
            try:
                original_filter = Filter(**self.dict(by_alias=by_alias))
            except ValidationError as e:
                raise RequestValidationError(e.raw_errors) from e
            return original_filter.sort(*args, **kwargs)

    return Depends(FilterWrapper)

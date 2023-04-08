from enum import Enum

from pydantic import validator
from pydantic.fields import ModelField
from sqlalchemy import or_
from sqlalchemy.orm import Query
from sqlalchemy.sql.selectable import Select

from ...base.filter import BaseFilterModel

_orm_operator_transformer = {
    'neq': lambda value: ('__ne__', value),
    'gt': lambda value: ('__gt__', value),
    'gte': lambda value: ('__ge__', value),
    'in': lambda value: ('in_', value),
    'isnull': lambda value: ('is_', None) if value is True else ('is_not', None),
    'lt': lambda value: ('__lt__', value),
    'lte': lambda value: ('__le__', value),
    'like': lambda value: ('like', f'%{value}%'),
    'ilike': lambda value: ('ilike', f'%{value}%'),
    'not': lambda value: ('is_not', value),
    'not_in': lambda value: ('not_in', value),
}


class Filter(BaseFilterModel):
    class Direction(str, Enum):
        asc = 'asc'
        desc = 'desc'

    @validator('*', pre=True)
    def split_str(cls, value: str, field: ModelField):
        if (
            field.name == cls.Constants.ordering_field_name
            or field.name.endswith('__in')
            or field.name.endswith('__not_in')
        ) and isinstance(value, str):
            return [field.type_(v) for v in value.split(',')]
        return value

    def filter(self, query: Query | Select):
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                query = field_value.filter(query)
            else:
                if '__' in field_name:
                    field_name, operator = field_name.split('__')
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = '__eq__'

                if field_name == self.Constants.search_field_name and hasattr(self.Constants, 'search_model_fields'):

                    def search_filter(field):
                        return getattr(self.Constants.model, field).ilike(f'%{value}%')

                    query = query.filter(or_(*list(map(search_filter, self.Constants.search_model_fields))))
                else:
                    model_field = getattr(self.Constants.model, field_name)
                    query = query.filter(getattr(model_field, operator)(value))

        return query

    def sort(self, query: Query | Select):
        if not self.ordering_values:
            return query

        for field_name in self.ordering_values:
            direction = Filter.Direction.asc
            if field_name.startswith('-'):
                direction = Filter.Direction.desc
            field_name = field_name.replace('-', '').replace('+', '')

            order_by_field = getattr(self.Constants.model, field_name)

            query = query.order_by(getattr(order_by_field, direction)())

        return query

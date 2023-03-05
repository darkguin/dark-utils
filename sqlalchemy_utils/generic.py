from sqlalchemy import and_
from sqlalchemy.orm import backref, foreign, relationship, remote


class generic_relationship:
    def __init__(self, object_type_fieldname: str, object_id_fieldname: str):
        self._object_type_fieldname = object_type_fieldname
        self._object_id_fieldname = object_id_fieldname

    @property
    def object_type_fieldname(self):
        return self._object_type_fieldname

    @property
    def object_id_fieldname(self):
        return self._object_id_fieldname

    def __set_name__(self, owner, name):
        self.basename = f'_{name}'
        print('BASENAME:', self.basename)

    def __get__(self, obj, objtype=None):
        object_type = getattr(obj, self.object_type_fieldname)
        name = f'{self.basename}_{object_type.lower()}'
        print('NAME AND OBJECT TYPE:', name, object_type)

        if not hasattr(obj, name):
            object_type_field = getattr(obj.__class__, self.object_type_fieldname)
            object_id_field = getattr(obj.__class__, self.object_id_fieldname)

            table = obj.__class__.metadata.tables[object_type.lower()]
            print(
                'DEBUG INFO:',
                obj.__class__,
                object_id_field,
                object_type_field,
                obj.__class__.__name__.lower(),
                table.name)

            object_relationship = relationship(
                object_type,
                primaryjoin=foreign(object_id_field) == remote(table.c.id),
                backref=backref(
                    f'{obj.__class__.__name__.lower()}_set',
                    primaryjoin=and_(
                        table.c.id == foreign(remote(object_id_field)),
                        object_type_field == object_type
                    )
                )
            )

            setattr(obj.__class__, name, object_relationship)

        return getattr(obj, name)

    def __set__(self, obj, value):
        setattr(obj, self.object_type_fieldname, value.__class__.__name__)
        setattr(obj, self.object_id_fieldname, value.id)

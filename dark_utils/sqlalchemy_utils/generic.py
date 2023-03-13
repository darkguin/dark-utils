from sqlalchemy import and_
from sqlalchemy.orm import backref, foreign, relationship, remote

from .utils import get_basename_for_generic_relationship


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

    def get_target_class_by_obj(self, obj, object_type):
        target_class = None
        for mapper in obj.registry.mappers:
            if mapper.class_.__tablename__ == object_type:
                target_class = mapper.class_
                break
        if target_class is None:
            raise Exception('Invalid object_type')

        return target_class

    def __set_name__(self, owner, name):
        self.basename = get_basename_for_generic_relationship(name)

    def __get__(self, obj, objtype=None):
        object_type = getattr(obj, self.object_type_fieldname)
        name = f'{self.basename}_{object_type}'
        source_class = obj.__class__

        if not hasattr(source_class, name):
            object_type_field = getattr(source_class, self.object_type_fieldname)
            object_id_field = getattr(source_class, self.object_id_fieldname)

            table = source_class.metadata.tables[object_type]
            target_class = self.get_target_class_by_obj(obj, object_type)

            object_relationship = relationship(
                target_class.__name__,
                primaryjoin=and_(
                    foreign(object_id_field) == remote(table.c.id),
                    object_type_field == object_type
                ),
                backref=backref(
                    f'{source_class.__tablename__}_set',
                    primaryjoin=and_(
                        table.c.id == foreign(remote(object_id_field)),
                        object_type_field == object_type
                    )
                )
            )

            setattr(source_class, name, object_relationship)

        return getattr(obj, name)

    def __set__(self, obj, value):
        setattr(obj, self.object_type_fieldname, value.__class__.__tablename__)
        setattr(obj, self.object_id_fieldname, value.id)


def attach_relationship(
    source_class,
    target_class,
    object_type_fieldname: str = 'object_type',
    object_id_fieldname: str = 'object_id',
    object_fieldname: str = 'object'
):
    object_type = target_class.__tablename__
    name = f'{get_basename_for_generic_relationship(object_fieldname)}_{object_type}'

    if not hasattr(source_class, name):
        object_type_field = getattr(source_class, object_type_fieldname)
        object_id_field = getattr(source_class, object_id_fieldname)

        object_relationship = relationship(
            target_class.__name__,
            primaryjoin=and_(
                foreign(object_id_field) == remote(target_class.__table__.c.id),
                object_type_field == object_type
            ),
            backref=backref(
                f'{source_class.__tablename__}_set',
                primaryjoin=and_(
                    target_class.__table__.c.id == foreign(remote(object_id_field)),
                    object_type_field == object_type
                )
            )
        )

        setattr(source_class, name, object_relationship)

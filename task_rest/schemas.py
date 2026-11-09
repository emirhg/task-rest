from marshmallow import Schema, fields, post_dump
from datetime import datetime


class TaskAnnotationSchema(Schema):
    description = fields.Str(required = True)
    entry = fields.DateTime(format="rfc", dump_only = True) # read-only


# BUG: README documents a "hide" field on POST, but it is not defined here, so
# unknown='EXCLUDE' (resources.py) silently drops it.
class TaskSchema(Schema):
    description = fields.Str(required = True)
    due = fields.DateTime(format="rfc", load_default=None)
    priority = fields.Str(load_default=None)
    project = fields.Str(load_default=None)
    recur = fields.Str(load_default=None)
    scheduled = fields.DateTime(format="rfc", load_default=None)
    start = fields.DateTime(format="rfc", load_default=None)
    tags = fields.List(fields.Str(), load_default=None)
    until = fields.DateTime(format="rfc", load_default=None)

    # read-only
    annotations = fields.List(fields.Nested(TaskAnnotationSchema), dump_only = True)
    depends = fields.List(fields.Nested(lambda: TaskSchema(exclude=("depends",))), dump_only = True)
    end = fields.DateTime(format="rfc", dump_only = True)
    entry = fields.DateTime(format="rfc", dump_only = True)
    id = fields.Int(dump_only=True)
    imask = fields.Int(dump_only=True)
    mask = fields.Str(dump_only=True)
    modified = fields.DateTime(format="rfc", dump_only=True)
    parent = fields.Nested(lambda: TaskSchema(exclude=("parent",)), dump_only=True)
    status = fields.Str(dump_only = True)
    urgency = fields.Float(dump_only= True)
    uuid = fields.Str(required = True, dump_only=True)

    @post_dump
    def remove_none_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items() if value != None
        }

    @post_dump
    def remove_empty_lists(self, data, **kwargs):
        return {
            key: value for key, value in data.items() if ((type(value) is not list) or value)
        }



# used to add or remove dependancies, usually uuid is not deserialized
class DependantTaskSchema(Schema):
    uuid = fields.Str(required = True)

from app.sql_warehouse.query.parser import validate_sql


class ValidateQuery:
    def execute(self, req, user):
        del user
        return validate_sql(req.sql, req.dialect)


def validate_query(req, user):
    return ValidateQuery().execute(req, user)

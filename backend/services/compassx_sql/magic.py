from IPython.core.magic import Magics, cell_magic, magics_class, needs_local_scope

from .client import sql


@magics_class
class CompassXSqlMagic(Magics):
    @needs_local_scope
    @cell_magic
    def sql(self, line, cell, local_ns=None):
        line = line.strip()
        df = sql(cell)
        if line:
            # `%%sql var_name`
            var_name = line.split()[0]
            if local_ns is not None:
                local_ns[var_name] = df
            else:
                self.shell.user_ns[var_name] = df
            return None
        return df


def load_ipython_extension(ipython):
    ipython.register_magics(CompassXSqlMagic)

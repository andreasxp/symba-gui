from functools import cache

@cache
def get_chart_function(code):
    exec(code, globals(), locals())

    try:
        return locals()["chart"]
    except KeyError:
        raise ValueError("Could not find chart in compiled code")

class Chart:
    def __init__(self, code):
        self.code = code
        self.func = get_chart_function(code)

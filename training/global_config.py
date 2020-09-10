from collections import defaultdict
from functools import partial
import inspect
from typing import Generic, TypeVar

T = TypeVar('T')
config: 'GlobalConfig'  # singleton, set below


class HyperParam(Generic[T]):
    """
    Simple type to indicate that a variable counts as a hyperparameter.
    """
    pass


def update_hyperparams(func=None, *, name=None):
    """
    Updates class variables and function parameters from global config.

    Usage::

        @update_hyperparams
        def foo(x, y, z: HyperParam = 1):
            ...

        @update_hyperparams('baz')
        class MyClass:
            val1: HyperParam
            val2: HyperParam = 3

    In the above example, the ``foo()`` function will automatically set a
    the default value ``config['foo.z'] = 1`` if that value does not
    already exist. If it does exist, then the function's default parameter
    value will be replaced with the one in the config.

    Likewise, the parameters ``MyClass.val1`` and ``MyClass.val2`` will be
    retrieved from ``config['baz.val1']`` and ``config['baz.val2']``,
    with the latter taking on a default value of 3 if it does not already exist.
    If the former doesn't exist, a ``ConfigError`` will be raised since a
    default value isn't supplied.

    Whenever the config gets updated, these function and class values will
    automatically get updated too.
    """
    if func is None:
        # use as a decorator, e.g.
        #   @update_hyperparams(name='foobar')
        return partial(update_hyperparams, name=name)
    if name is None:
        name = func.__name__.lower()
    base_name = name + '.' if name else ''

    if inspect.isclass(func):
        for name, annotation in func.__annotations__.items():
            cname = base_name + name
            if issubclass(annotation, HyperParam):
                def update_param(val, name=name, obj=func):
                    setattr(obj, name, val)
                if hasattr(func, name):
                    val = config.setdefault(cname, getattr(func, name))
                else:
                    val = config[cname]
                config.addhook(cname, update_param)
                update_param(val)
        return func

    elif callable(func):
        wrapper = partial(func)
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            cname = base_name + name
            if issubclass(param.annotation, HyperParam):
                def update_param(val, name=name, wrapper=wrapper):
                    wrapper.keywords[name] = val
                if param.default is not sig.empty:
                    val = config.setdefault(cname, param.default)
                else:
                    val = config[cname]
                config.addhook(cname, update_param)
                update_param(val)
        return wrapper

    else:
        raise ValueError(f"'{func}' is not callable.")


class GlobalConfig(dict):
    """
    Global configuration object.

    This is a simple subclass of a dictionary to allow for callbacks whenever
    a new item is set.
    """

    def __str__(self):
        return "GlobalConfig(%s)" % super().__str__()

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        # Hooks get called whenever attributes get set.
        # This allows us to update hyperparameters in other places in the code,
        # e.g. in function signatures and class parameters.
        self._hooks = defaultdict(list)

    def __setitem__(self, name, val):
        super().__setitem__(name, val)
        for hook in self._hooks[name]:
            hook(val)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        # Just run all of the hooks for simplicity.
        for key, hooks in self._hooks.items():
            if key in self:
                val = self[key]
                for hook in hooks:
                    hook(val)

    def addhook(self, name, hook):
        self._hooks[name].append(hook)


config = GlobalConfig()

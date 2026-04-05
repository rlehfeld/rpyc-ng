"""
Utilities (not part of the core protocol)
"""
import inspect
from rpyc.core import DEFAULT_CONFIG


_UNSET = object()


def service(exposed_prefix, cls=_UNSET):
    """find and rename exposed decorated attributes"""
    if cls is _UNSET:
        if inspect.isclass(exposed_prefix):
            cls = exposed_prefix
            exposed_prefix = DEFAULT_CONFIG['exposed_prefix']
        else:
            def wrapper(cls):
                return service(exposed_prefix, cls)
            wrapper.__name__ = service.__name__
            wrapper.__doc__ = service.__doc__
            return wrapper

    if not isinstance(exposed_prefix, str):
        raise TypeError('exposed_prefix must be a string')
    if not inspect.isclass(cls):
        raise TypeError('cls must be a class')

    prev_exposed_prefix = getattr(cls, '__exposed_', _UNSET)
    if prev_exposed_prefix is not _UNSET:
        if prev_exposed_prefix != exposed_prefix:
            raise RuntimeError(
                'multiple use of rpyc.service with different expose prefixes: '
                f'{prev_exposed_prefix!r} != {exposed_prefix!r}'
            )

    # NOTE: inspect.getmembers invokes getattr for each attribute-name. Descriptors may raise AttributeError.
    # Only the AttributeError exception is caught when raised. This decorator will if a descriptor raises
    # any exception other than AttributeError when getattr is called.
    for attr_name, attr_obj in inspect.getmembers(cls):  # rebind exposed decorated attributes
        attr_exposed_prefix = getattr(attr_obj, '__exposed__', False)
        if (attr_exposed_prefix and
                not attr_name.startswith(attr_exposed_prefix) and
                not inspect.iscode(attr_obj)):  # exclude the implementation
            renamed = attr_exposed_prefix + attr_name
            if not hasattr(cls, renamed):
                setattr(cls, renamed, attr_obj)

    cls.__exposed__ = exposed_prefix
    return cls


def exposed(exposed_prefix, exposed_obj=_UNSET):
    """decorator that adds the exposed prefix information to functions which `service` uses to rebind attrs"""
    if exposed_obj is _UNSET:
        if isinstance(exposed_prefix, str):
            def wrapper(exposed_obj):
                return exposed(exposed_prefix, exposed_obj)
            wrapper.__name__ = exposed.__name__
            wrapper.__doc__ = exposed.__doc__
            return wrapper

        exposed_obj = exposed_prefix
        exposed_prefix = DEFAULT_CONFIG['exposed_prefix']

    if not isinstance(exposed_prefix, str):
        raise TypeError('exposed_prefix must be a string')

    if inspect.isclass(exposed_obj):
        raise TypeError('exposed should not be used with classes')

    if hasattr(exposed_obj, '__call__') or hasattr(exposed_obj, '__get__'):
        # When the arg is callable (i.e. `@rpyc.exposed`) then use default prefix and invoke
        exposed_obj.__exposed__ = exposed_prefix
        return exposed_obj

    raise TypeError('exposed_obj must be a callable object or a descriptor')

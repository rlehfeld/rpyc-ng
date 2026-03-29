"""*NetRef*: a transparent *network reference*. This module contains quite a lot
of *magic*, so beware.
"""
import sys
import types
from rpyc.lib import get_methods, get_id_pack
from rpyc.lib.compat import pickle, maxint
from rpyc.core import consts


builtin_id_pack_cache = {}  # name_pack -> id_pack
builtin_classes_cache = {}  # id_pack -> class
# If these can be accessed, numpy will try to load the array from local memory,
# resulting in exceptions and/or segfaults, see #236:
DELETED_ATTRS = frozenset([
    '__array_struct__', '__array_interface__',
])

"""the set of attributes that are local to the netref object"""
LOCAL_ATTRS = frozenset([
    '____conn__', '____id_pack__', '____refcount__', '____hash__', '____member__', '____bind_instance__',
    '__class__', '__cmp__', '__del__', '__delattr__',
    '__dir__', '__getattr__', '__getattribute__', '__hash__',
    '__instancecheck__', '__subclasscheck__', '__subclasses__',
    '__init__', '__metaclass__', '__module__', '__new__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__slots__', '__str__', '__bool__',
    '__weakref__', '__dict__', '__methods__', '__exit__',
    '__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__',
    'mro', '__mro__', '__bases__', '__base__',
]) | DELETED_ATTRS

"""a list of types considered built-in (shared between connections)
this is needed because iterating the members of the builtins module is not enough,
some types (e.g NoneType) are not members of the builtins module.
TODO: this list is not complete.
"""
_builtin_types = [
    type, object, bool, complex, dict, float, int, list, slice, str, tuple, set,
    frozenset, BaseException, Exception, type(None), types.BuiltinFunctionType, types.GeneratorType,
    types.MethodType, types.CodeType, types.FrameType, types.TracebackType,
    types.ModuleType, types.FunctionType, types.MappingProxyType,

    type(int.__add__),      # wrapper_descriptor
    type((1).__add__),      # method-wrapper
    type(iter([])),         # listiterator
    type(iter(())),         # tupleiterator
    type(iter(set())),      # setiterator
    bytes, bytearray, type(iter(range(10))), memoryview
]
_normalized_builtin_types = {}


def syncreq(proxy, handler, *args):
    """Performs a synchronous request on the given proxy object.
    Not intended to be invoked directly.

    :param proxy: the proxy on which to issue the request
    :param handler: the request handler (one of the ``HANDLE_XXX`` members of
                    ``rpyc.protocol.consts``)
    :param args: arguments to the handler

    :raises: any exception raised by the operation will be raised
    :returns: the result of the operation
    """
    if type(proxy) is NetrefMetaclass:
        base = type
    else:
        base = object
    conn = base.__getattribute__(proxy, "____conn__")
    return conn.sync_request(handler, proxy, *args)


def asyncreq(proxy, handler, *args):
    """Performs an asynchronous request on the given proxy object.
    Not intended to be invoked directly.

    :param proxy: the proxy on which to issue the request
    :param handler: the request handler (one of the ``HANDLE_XXX`` members of
                    ``rpyc.protocol.consts``)
    :param args: arguments to the handler

    :returns: an :class:`~rpyc.core.async_.AsyncResult` representing
              the operation
    """
    if type(proxy) is NetrefMetaclass:
        base = type
    else:
        base = object
    conn = base.__getattribute__(proxy, "____conn__")
    return conn.async_request(handler, proxy, *args)


class Member:
    __slots__ = "____conn__", "____id_pack__", "____refcount__", "____hash__"


class MemberDescriptor:
    __slots__ = '_name', '_owner', '_default'

    def __init__(self, default=None, /):
        self._default = default
        self._owner = None
        self._name = None

    def __set_name__(self, owner, name, /):
        self._owner = owner
        self._name = name

    def __get__(self, instance, owner, /):
        if instance is None:
            return self._default
        return getattr(instance.____member__, self._name, self._default)

    def __set__(self, instance, value, /):
        setattr(instance.____member__, self._name, value)

    def __delete__(self, instance):
        delattr(instance.____member__, self._name)


class NetrefMetaclass(type):
    """A *metaclass* used to customize the ``__repr__`` of ``netref`` classes.
    It is quite useless, but it makes debugging and interactive programming
    easier"""
    __slots__ = ()

    def __new__(metacls, name, bases, dct, id_pack=None):
        alldct = {}
        for b in reversed(bases):
            alldct.update(b.__dict__)
        alldct.update(dct)

        for attr in LOCAL_ATTRS:
            if attr not in alldct and attr not in (
                    '__class__',
                    '__methods__',
                    '__metaclass__',
                    '__weakref__',
                    '__array_interface__',
                    '__array_struct__',
                    '__repr__',
                    '__dict__',
                    '__reduce__',
                    '__instancecheck__',
                    '__subclasscheck__',
                    '__subclasses__',
                    '__init__',
                    '__new__',
                    '____id_pack__',
                    '____refcount__',
                    '____conn__',
                    '____hash__',
                    '____member__',
                    '____bind_instance__',
                    'mro',
                    '__mro__',
                    '__bases__',
                    '__base__',
            ):
                dct[attr] = metacls.__dict__[attr]

        for attr in (
                '____refcount__',
                '____conn__',
                '____hash__',
        ):
            if attr not in alldct:
                dct[attr] = None

        dct['____id_pack__'] = id_pack

        undefined = object()
        for attr in (
                '____refcount__',
                '____conn__',
                '____id_pack__',
                '____hash__',
        ):
            value = dct.get(attr, undefined)
            if value is not undefined and not isinstance(value, MemberDescriptor):
                dct[attr] = MemberDescriptor(dct[attr])

        return super(NetrefMetaclass, metacls).__new__(metacls, name, bases, dct)

    def __call__(cls, *args, **kwargs):
        kwargs = tuple(kwargs.items())
        return syncreq(cls, consts.HANDLE_CALL, args, kwargs)

    def ____bind_instance__(cls, conn, id_pack):
        obj = cls.__new__(cls, conn, id_pack)
        if isinstance(obj, cls):
            cls.__init__(obj, conn, id_pack)
        return obj

    def __del__(self):
        if self.____id_pack__ is not None:
            try:
                asyncreq(self, consts.HANDLE_DEL, self.____refcount__)
            except Exception:
                # raised in a destructor, most likely on program termination,
                # when the connection might have already been closed.
                # it's safe to ignore all exceptions here
                pass

    def __getattribute__(self, name):
        if type(self) is NetrefMetaclass:
            base = type
        else:
            base = object
        if type(self) is NetrefMetaclass and name in ("__name__", ):
            return base.__getattribute__(self, name)
        if name in LOCAL_ATTRS:
            if name == "__class__":
                cls = base.__getattribute__(self, "__class__")
                if cls is None:
                    cls = self.__getattr__("__class__")
                return cls
            if name in DELETED_ATTRS:
                raise AttributeError()
            return base.__getattribute__(self, name)
        if name in ("__call__", "__array__"):
            return base.__getattribute__(self, name)
        return syncreq(self, consts.HANDLE_GETATTR, name)

    def __getattr__(self, name):
        if name in DELETED_ATTRS:
            raise AttributeError()
        if name != '__class__' and name in LOCAL_ATTRS:
            raise AttributeError()
        return syncreq(self, consts.HANDLE_GETATTR, name)

    def __delattr__(self, name):
        if name in LOCAL_ATTRS:
            super(type(self), self).__delattr__(name)
        else:
            syncreq(self, consts.HANDLE_DELATTR, name)

    def __setattr__(self, name, value):
        if name in LOCAL_ATTRS:
            if (name in (
                    '____conn__',
                    '____id_pack__',
                    '____refcount__',
                    '____hash__'
                    ) and type(self) is NetrefMetaclass and
                    not isinstance(value, MemberDescriptor)):
                value = MemberDescriptor(value)
                value.__set_name__(self, name)
            if type(self) is NetrefMetaclass:
                base = type
            else:
                base = object
            base.__setattr__(self, name, value)
        else:
            syncreq(self, consts.HANDLE_SETATTR, name, value)

    def __dir__(self):
        return list(syncreq(self, consts.HANDLE_DIR))

    def __repr__(self):
        if self.____conn__ is None:
            if self.__module__:
                return f"<netref class '{self.__module__}.{self.__name__}'>"
            return f"<netref class '{self.__name__}'>"
        return syncreq(self, consts.HANDLE_REPR)

    def __str__(self):
        return syncreq(self, consts.HANDLE_STR)

    def __bool__(self):
        return syncreq(self, consts.HANDLE_BOOL)

    def __exit__(self, exc, typ, tb):
        return syncreq(self, consts.HANDLE_CTXEXIT, exc)  # can't pass type nor traceback

    def __reduce_ex__(self, proto):
        # support for pickling netrefs
        return pickle.loads, (syncreq(self, consts.HANDLE_PICKLE, proto),)

    def __instancecheck__(self, other):
        # support for checking cached instances across connections
        if super(type(self), self).__instancecheck__(other):
            if self is BaseNetref:
                return True
            if self.____id_pack__[2] != 0:
                raise TypeError("isinstance() arg 2 must be a class, type, or tuple of classes and types")
            elif self.____id_pack__[1] == other.____id_pack__[1]:
                return other.____id_pack__[2] != 0
            else:
                # seems dubious if each netref proxies to a different address spaces
                return syncreq(self, consts.HANDLE_INSTANCECHECK, other.____id_pack__)
        if self.____id_pack__ is None:
            return False
        if self.____id_pack__[2] == 0:
            # outside the context of `__instancecheck__`, `__class__` is expected to be type(self)
            # within the context of `__instancecheck__`, `other` should be compared to the proxied class
            return isinstance(other, self.__dict__['__class__'].instance)
        raise TypeError("isinstance() arg 2 must be a class, type, or tuple of classes and types")

    def __subclasscheck__(self, other):
        # support for checking cached instances across connections
        if super(type(self), self).__subclasscheck__(other):
            if self is BaseNetref:
                return True
            if self.____id_pack__[2] != 0:
                raise TypeError("isinstance() arg 2 must be a class, type, or tuple of classes and types")
            elif self.____id_pack__[1] == other.____id_pack__[1]:
                return other.____id_pack__[2] == 0
            else:
                # seems dubious if each netref proxies to a different address spaces
                return syncreq(self, consts.HANDLE_SUBCLASSCHECK, other.____id_pack__)
        if self.____id_pack__ is None:
            return False
        if self.____id_pack__[2] == 0:
            # outside the context of `__instancecheck__`, `__class__` is expected to be type(self)
            # within the context of `__instancecheck__`, `other` should be compared to the proxied class
            return issubclass(other, self.__dict__['__class__'].instance)
        raise TypeError("isinstance() arg 2 must be a class, type, or tuple of classes and types")

    def __hash__(self):
        # cache hashes for performance reasons
        if self.____hash__ is None:
            if self.____conn__ is None:
                return super(type(self), self).__hash__()
            try:
                self.____hash__ = syncreq(self, consts.HANDLE_HASH)
            except BaseException as ex:
                self.____hash__ = ex
        if isinstance(self.____hash__, BaseException):
            raise self.____hash__ from None
        return self.____hash__


class BaseNetref(metaclass=NetrefMetaclass):
    """The base netref class, from which all netref classes derive. Some netref
    classes are "pre-generated" and cached upon importing this module (those
    defined in the :data:`_builtin_types`), and they are shared between all
    connections.

    The rest of the netref classes are created by :meth:`rpyc.core.protocol.Connection._unbox`,
    and are private to the connection.

    Do not use this class directly; use :func:`class_factory` instead.

    :param conn: the :class:`rpyc.core.protocol.Connection` instance
    :param id_pack: id tuple for an object ~ (name_pack, remote-class-id, remote-instance-id)
        (cont.) name_pack := __module__.__name__ (hits or misses on builtin cache and sys.module)
                remote-class-id := id of object class (hits or misses on netref classes cache and instance checks)
                remote-instance-id := id object instance (hits or misses on proxy cache)
        id_pack is usually created by rpyc.lib.get_id_pack
    """
    __slots__ = "__weakref__", "____member__"
    ____refcount__ = 1

    def __cmp__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__cmp__')

    def __eq__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__eq__')

    def __ne__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__ne__')

    def __lt__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__lt__')

    def __gt__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__gt__')

    def __le__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__le__')

    def __ge__(self, other):
        return syncreq(self, consts.HANDLE_CMP, other, '__ge__')

    def __repr__(self):
        return syncreq(self, consts.HANDLE_REPR)

    def __init__(self, conn, id_pack):
        self.____member__ = Member()
        self.____conn__ = conn
        self.____id_pack__ = id_pack
        self.____refcount__ = 1
        self.____hash__ = None


class Method:
    __slots__ = ('__name__', '__doc__')

    def __init__(self, name, doc):
        self.__name__ = name
        self.__doc__ = doc

    def __get__(self, instance, owner=None):
        if instance is None:
            instance = owner
        return syncreq(instance, consts.HANDLE_GETATTR, self.__name__)

    def __set__(self, instance, value):
        return syncreq(instance, consts.HANDLE_SETATTR, self.__name__)

    def __delete__(self, instance):
        return syncreq(instance, consts.HANDLE_DELATTR, self.__name__)


def _make_method(name, doc):
    """creates a method with the given name and docstring that invokes
    :func:`syncreq` on its `self` argument"""

    slicers = {"__getslice__": "__getitem__", "__delslice__": "__delitem__", "__setslice__": "__setitem__"}

    name = str(name)                                      # IronPython issue #10
    if name == "__call__":
        def __call__(_self, *args, **kwargs):
            kwargs = tuple(kwargs.items())
            return syncreq(_self, consts.HANDLE_CALL, args, kwargs)
        __call__.__doc__ = doc
        return __call__
    if name in slicers:                                 # 32/64 bit issue #41
        def method(self, start, stop, *args):
            if stop == maxint:
                stop = None
            return syncreq(self, consts.HANDLE_OLDSLICING, slicers[name], name, start, stop, args)
        method.__name__ = name
        method.__doc__ = doc
        return method
    if name == "__array__":
        def __array__(self, *args, **kwargs):
            # Note that protocol=-1 will only work between python
            # interpreters of the same version.
            if type(self) is NetrefMetaclass:
                base = type
            else:
                base = object
            if not base.__getattribute__(self, '____conn__')._config["allow_pickle"]:
                # Security check that server side allows pickling per #551
                raise ValueError("pickling is disabled")
            array = pickle.loads(syncreq(self, consts.HANDLE_PICKLE, -1))
            return array.__array__(*args, **kwargs)
        __array__.__doc__ = doc
        return __array__
    return Method(name, doc)


class NetrefClass:
    """a descriptor of the class being proxied

    Future considerations:
     + there may be a cleaner alternative but lib.compat.with_metaclass prevented using __new__
     + consider using __slot__ for this class
     + revisit the design choice to use properties here
    """

    def __init__(self, class_obj):
        self._class_obj = class_obj

    @property
    def instance(self):
        """accessor to class object for the instance being proxied"""
        return self._class_obj

    @property
    def owner(self):
        """accessor to the class object for the instance owner being proxied"""
        return self._class_obj.__class__

    def __get__(self, netref_instance, netref_owner):
        """the value returned when accessing the netref class is dictated by whether or not an instance is proxied"""
        if netref_instance is None:
            return self.owner
        return self.instance


def class_factory(id_pack, methods, conn=None):
    """Creates a netref class proxying the given class

    :param id_pack: the id pack used for proxy communication
    :param methods: a list of ``(method name, docstring)`` tuples, of the methods that the class defines

    :returns: a netref class
    """
    ns = {"__slots__": (), "__class__": None}
    name_pack = id_pack[0]
    class_descriptor = None
    if name_pack is not None:
        # attempt to resolve __class__ using normalized builtins first
        _builtin_class = _normalized_builtin_types.get(name_pack)
        if _builtin_class is not None:
            class_descriptor = NetrefClass(_builtin_class)
        # then by imported modules (this also tries all builtins under "builtins")
        else:
            _module = None
            cursor = len(name_pack)
            while cursor != -1:
                _module = sys.modules.get(name_pack[:cursor])
                if _module is None:
                    cursor = name_pack[:cursor].rfind('.')
                    continue
                _class_name = name_pack[cursor + 1:]
                _class = getattr(_module, _class_name, None)
                if _class is not None and hasattr(_class, '__class__'):
                    class_descriptor = NetrefClass(_class)
                elif _class is None:
                    class_descriptor = NetrefClass(type(_module))
                break
    if class_descriptor is not None:
        ns['__class__'] = class_descriptor
    # create methods that must perform a syncreq
    for name, doc in methods:
        name = str(name)  # IronPython issue #10
        # only create methods that won't shadow BaseNetref during merge for mro
        if name not in LOCAL_ATTRS:  # i.e. `name != __class__`
            ns[name] = _make_method(name, doc)
    netref_cls = type(name_pack, (BaseNetref, ), ns)
    netref_cls.____id_pack__ = id_pack
    netref_cls.____conn__ = conn
    return netref_cls


for _builtin in _builtin_types:
    _id_pack = get_id_pack(_builtin)
    _name_pack = _id_pack[0]
    _normalized_builtin_types[_name_pack] = _builtin
    _builtin_methods = get_methods(LOCAL_ATTRS, _builtin)
    # assume all normalized builtins are classes
    builtin_classes_cache[_name_pack] = class_factory(_id_pack, _builtin_methods)

"""*Brine* is a simple, fast and secure object serializer for **immutable** objects.

The following types are supported: ``int``, ``bool``, ``str``, ``float``,
``unicode``, ``bytes``, ``slice``, ``complex``, ``tuple`` (of simple types),
``frozenset`` (of simple types) as well as the following singletons: ``None``,
``NotImplemented``, and ``Ellipsis``.

Example::
 >>> x = ("he", 7, u"llo", 8, (), 900, None, True, Ellipsis, 18.2, 18.2j + 13,
 ... slice(1,2,3), frozenset([5,6,7]), NotImplemented)
 >>> dumpable(x)
 True
 >>> y = dump(x)
 >>> y.encode("hex")
 '140e0b686557080c6c6c6f580216033930300003061840323333333333331b402a000000000000403233333333333319125152531a1255565705'
 >>> z = load(y)
 >>> x == z
 True
"""
from rpyc.lib.compat import Struct, BytesIO, BYTES_LITERAL


# singletons
TAG_NONE = b"\x00"
TAG_EMPTY_STR = b"\x01"
TAG_EMPTY_TUPLE = b"\x02"
TAG_TRUE = b"\x03"
TAG_FALSE = b"\x04"
TAG_NOT_IMPLEMENTED = b"\x05"
TAG_ELLIPSIS = b"\x06"
# types
TAG_UNICODE = b"\x08"
# deprecated w/ py2 support TAG_LONG = b"\x09"
TAG_STR1 = b"\x0a"
TAG_STR2 = b"\x0b"
TAG_STR3 = b"\x0c"
TAG_STR4 = b"\x0d"
TAG_STR_L1 = b"\x0e"
TAG_STR_L4 = b"\x0f"
TAG_TUP1 = b"\x10"
TAG_TUP2 = b"\x11"
TAG_TUP3 = b"\x12"
TAG_TUP4 = b"\x13"
TAG_TUP_L1 = b"\x14"
TAG_TUP_L4 = b"\x15"
TAG_INT_L1 = b"\x16"
TAG_INT_L4 = b"\x17"
TAG_FLOAT = b"\x18"
TAG_SLICE = b"\x19"
TAG_FSET = b"\x1a"
TAG_COMPLEX = b"\x1b"
TAG_NONETYPE = b"\x1c"
TAG_INTTYPE = b"\x1d"
TAG_BOOLTYPE = b"\x1e"
TAG_FLOATTYPE = b"\x1f"
TAG_BYTESTYPE = b"\x20"
TAG_STRTYPE = b"\x21"
TAG_COMPLEXTYPE = b"\x22"
TAG_NOTIMPLEMENTEDTYPE = b"\x23"
TAG_ELLIPSISTYPE = b"\x24"

IMM_INTS = dict((i, bytes([i + 0x50])) for i in range(-0x30, 0xa0))

# Below "!" is used to set byte order as network (= big-endian). See https://docs.python.org/3/library/struct.html
F8 = Struct("!d")  # Python type float w/ size [8] (ctype double)
C16 = Struct("!dd")  # Successive floats (complex numbers)
I1 = Struct("!B")  # Python type int w/ size [1] (ctype unsigned char)
I4 = Struct("!L")  # Python type int w/ size [4] (ctype unsigned long)
# I8I8 is successive ints w/ size 8 and was introduced to pack local thread id and remote thread id. Since
# PyThread_get_thread_ident returns a type of unsigned long, a platform dependent size, we
# need 8 bytes of length to support LP64/64-bit platforms. See
#  - https://unix.org/whitepapers/64bit.html
#  - https://en.wikipedia.org/wiki/Integer_(computer_science)#Long_integer
# TODO: Switch to native_id when 3.7 is EOL b/c PyThread_get_thread_ident is inheritly hosed due to casting.
I8I8 = Struct("!QQ")

_dump_type_registry = {}
_dump_registry = {}
_load_registry = {}
IMM_INTS_LOADER = dict((v, k) for k, v in IMM_INTS.items())


def register(coll, key):
    def deco(func):
        coll[key] = func
        return func
    return deco


# ===============================================================================
# dumping
# ===============================================================================
@register(_dump_registry, type(None))
def _dump_none(obj, stream):
    stream.append(TAG_NONE)


@register(_dump_registry, type(NotImplemented))
def _dump_notimplemeted(obj, stream):
    stream.append(TAG_NOT_IMPLEMENTED)


@register(_dump_registry, type(Ellipsis))
def _dump_ellipsis(obj, stream):
    stream.append(TAG_ELLIPSIS)


@register(_dump_registry, bool)
def _dump_bool(obj, stream):
    if obj:
        stream.append(TAG_TRUE)
    else:
        stream.append(TAG_FALSE)


@register(_dump_registry, slice)
def _dump_slice(obj, stream):
    stream.append(TAG_SLICE)
    _dump((obj.start, obj.stop, obj.step), stream)


@register(_dump_registry, frozenset)
def _dump_frozenset(obj, stream):
    stream.append(TAG_FSET)
    _dump(tuple(obj), stream)


@register(_dump_registry, int)
def _dump_int(obj, stream):
    if obj in IMM_INTS:
        stream.append(IMM_INTS[obj])
    else:
        obj = BYTES_LITERAL(str(obj))
        lenobj = len(obj)
        if lenobj < 256:
            stream.append(TAG_INT_L1 + I1.pack(lenobj) + obj)
        else:
            stream.append(TAG_INT_L4 + I4.pack(lenobj) + obj)


@register(_dump_registry, float)
def _dump_float(obj, stream):
    stream.append(TAG_FLOAT + F8.pack(obj))


@register(_dump_registry, complex)
def _dump_complex(obj, stream):
    stream.append(TAG_COMPLEX + C16.pack(obj.real, obj.imag))


@register(_dump_registry, bytes)
def _dump_bytes(obj, stream):
    lenobj = len(obj)
    if lenobj == 0:
        stream.append(TAG_EMPTY_STR)
    elif lenobj == 1:
        stream.append(TAG_STR1 + obj)
    elif lenobj == 2:
        stream.append(TAG_STR2 + obj)
    elif lenobj == 3:
        stream.append(TAG_STR3 + obj)
    elif lenobj == 4:
        stream.append(TAG_STR4 + obj)
    elif lenobj < 256:
        stream.append(TAG_STR_L1 + I1.pack(lenobj) + obj)
    else:
        stream.append(TAG_STR_L4 + I4.pack(lenobj) + obj)


@register(_dump_registry, type(u""))
def _dump_str(obj, stream):
    stream.append(TAG_UNICODE)
    _dump_bytes(obj.encode("utf8"), stream)


@register(_dump_registry, tuple)
def _dump_tuple(obj, stream):
    lenobj = len(obj)
    if lenobj == 0:
        stream.append(TAG_EMPTY_TUPLE)
    elif lenobj == 1:
        stream.append(TAG_TUP1)
    elif lenobj == 2:
        stream.append(TAG_TUP2)
    elif lenobj == 3:
        stream.append(TAG_TUP3)
    elif lenobj == 4:
        stream.append(TAG_TUP4)
    elif lenobj < 256:
        stream.append(TAG_TUP_L1 + I1.pack(lenobj))
    else:
        stream.append(TAG_TUP_L4 + I4.pack(lenobj))
    for item in obj:
        _dump(item, stream)


@register(_dump_type_registry, type(None))
def _dump_nonetype(obj, stream):
    stream.append(TAG_NONETYPE)


@register(_dump_type_registry, int)
def _dump_inttype(obj, stream):
    stream.append(TAG_INTTYPE)


@register(_dump_type_registry, bool)
def _dump_booltype(obj, stream):
    stream.append(TAG_BOOLTYPE)


@register(_dump_type_registry, float)
def _dump_floattype(obj, stream):
    stream.append(TAG_FLOATTYPE)


@register(_dump_type_registry, bytes)
def _dump_bytestype(obj, stream):
    stream.append(TAG_BYTESTYPE)


@register(_dump_type_registry, str)
def _dump_strtype(obj, stream):
    stream.append(TAG_STRTYPE)


@register(_dump_type_registry, complex)
def _dump_complextype(obj, stream):
    stream.append(TAG_COMPLEXTYPE)


@register(_dump_type_registry, type(NotImplemented))
def _dump_notimplementedtype(obj, stream):
    stream.append(TAG_NOTIMPLEMENTEDTYPE)


@register(_dump_type_registry, type(Ellipsis))
def _dump_elipsistype(obj, stream):
    stream.append(TAG_ELLIPSISTYPE)


def _undumpable(obj, stream):
    raise TypeError(f"cannot dump {obj}")


def _dumptype(obj, stream):
    _dump_type_registry.get(obj, _undumpable)(obj, stream)


def _dump(obj, stream):
    _dump_registry.get(type(obj), _dumptype)(obj, stream)


# ===============================================================================
# loading
# ===============================================================================
@register(_load_registry, TAG_NONE)
def _load_none(stream):
    return None


@register(_load_registry, TAG_NOT_IMPLEMENTED)
def _load_nonimp(stream):
    return NotImplemented


@register(_load_registry, TAG_ELLIPSIS)
def _load_elipsis(stream):
    return Ellipsis


@register(_load_registry, TAG_TRUE)
def _load_true(stream):
    return True


@register(_load_registry, TAG_FALSE)
def _load_false(stream):
    return False


@register(_load_registry, TAG_EMPTY_TUPLE)
def _load_empty_tuple(stream):
    return ()


@register(_load_registry, TAG_EMPTY_STR)
def _load_empty_str(stream):
    return b""


@register(_load_registry, TAG_FLOAT)
def _load_float(stream):
    return F8.unpack(stream.read(8))[0]


@register(_load_registry, TAG_COMPLEX)
def _load_complex(stream):
    real, imag = C16.unpack(stream.read(16))
    return complex(real, imag)


@register(_load_registry, TAG_STR1)
def _load_str1(stream):
    return stream.read(1)


@register(_load_registry, TAG_STR2)
def _load_str2(stream):
    return stream.read(2)


@register(_load_registry, TAG_STR3)
def _load_str3(stream):
    return stream.read(3)


@register(_load_registry, TAG_STR4)
def _load_str4(stream):
    return stream.read(4)


@register(_load_registry, TAG_STR_L1)
def _load_str_l1(stream):
    l, = I1.unpack(stream.read(1))
    return stream.read(l)


@register(_load_registry, TAG_STR_L4)
def _load_str_l4(stream):
    l, = I4.unpack(stream.read(4))
    return stream.read(l)


@register(_load_registry, TAG_UNICODE)
def _load_unicode(stream):
    obj = _load(stream)
    return obj.decode("utf-8")


@register(_load_registry, TAG_TUP1)
def _load_tup1(stream):
    return (_load(stream),)


@register(_load_registry, TAG_TUP2)
def _load_tup2(stream):
    return (_load(stream), _load(stream))


@register(_load_registry, TAG_TUP3)
def _load_tup3(stream):
    return (_load(stream), _load(stream), _load(stream))


@register(_load_registry, TAG_TUP4)
def _load_tup4(stream):
    return (_load(stream), _load(stream), _load(stream), _load(stream))


@register(_load_registry, TAG_TUP_L1)
def _load_tup_l1(stream):
    l, = I1.unpack(stream.read(1))
    return tuple(_load(stream) for i in range(l))


@register(_load_registry, TAG_TUP_L4)
def _load_tup_l4(stream):
    l, = I4.unpack(stream.read(4))
    return tuple(_load(stream) for i in range(l))


@register(_load_registry, TAG_SLICE)
def _load_slice(stream):
    start, stop, step = _load(stream)
    return slice(start, stop, step)


@register(_load_registry, TAG_FSET)
def _load_frozenset(stream):
    return frozenset(_load(stream))


@register(_load_registry, TAG_INT_L1)
def _load_int_l1(stream):
    l, = I1.unpack(stream.read(1))
    return int(stream.read(l))


@register(_load_registry, TAG_INT_L4)
def _load_int_l4(stream):
    l, = I4.unpack(stream.read(4))
    return int(stream.read(l))


@register(_load_registry, TAG_NONETYPE)
def _load_nonetype(stream):
    return type(None)


@register(_load_registry, TAG_INTTYPE)
def _load_inttype(stream):
    return int


@register(_load_registry, TAG_BOOLTYPE)
def _load_booltype(stream):
    return bool


@register(_load_registry, TAG_FLOATTYPE)
def _load_floattype(stream):
    return float


@register(_load_registry, TAG_BYTESTYPE)
def _load_bytestype(stream):
    return bytes


@register(_load_registry, TAG_STRTYPE)
def _load_strtype(stream):
    return str


@register(_load_registry, TAG_COMPLEXTYPE)
def _load_complextype(stream):
    return complex


@register(_load_registry, type(NotImplemented))
def _load_notimplementedtype(stream):
    return type(NotImplemented)


@register(_load_registry, type(Ellipsis))
def _load_ellipsistype(stream):
    return type(Ellipsis)


def _load(stream):
    tag = stream.read(1)
    if tag in IMM_INTS_LOADER:
        return IMM_INTS_LOADER[tag]
    return _load_registry.get(tag)(stream)

# ===============================================================================
# API
# ===============================================================================


def dump(obj):
    """Converts (dumps) the given object to a byte-string representation

    :param obj: any :func:`dumpable` object

    :returns: a byte-string representation of the object
    """
    stream = []
    _dump(obj, stream)
    return b"".join(stream)


def load(data):
    """Recreates (loads) an object from its byte-string representation

    :param data: the byte-string representation of an object

    :returns: the dumped object
    """
    stream = BytesIO(data)
    return _load(stream)


simple_types = frozenset([type(None), int, bool, float, bytes, str, complex, type(NotImplemented), type(Ellipsis)])


def dumpable(obj):
    """Indicates whether the given object is *dumpable* by brine

    :returns: ``True`` if the object is dumpable (e.g., :func:`dump` would succeed),
              ``False`` otherwise
    """
    if type(obj) is type and obj in simple_types:
        return True
    if type(obj) in simple_types:
        return True
    if type(obj) in (tuple, frozenset):
        return all(dumpable(item) for item in obj)
    if type(obj) is slice:
        return dumpable(obj.start) and dumpable(obj.stop) and dumpable(obj.step)
    return False


if __name__ == "__main__":
    import doctest
    doctest.testmod()

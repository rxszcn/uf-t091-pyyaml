
__all__ = ['BaseLoader', 'FullLoader', 'SafeLoader', 'Loader', 'UnsafeLoader',
        'SafeLoaderNoSexagesimal', 'FullLoaderNoSexagesimal',
        'UnsafeLoaderNoSexagesimal']

from .reader import *
from .scanner import *
from .parser import *
from .composer import *
from .constructor import *
from .resolver import *

class BaseLoader(Reader, Scanner, Parser, Composer, BaseConstructor, BaseResolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        BaseConstructor.__init__(self)
        BaseResolver.__init__(self)

class FullLoader(Reader, Scanner, Parser, Composer, FullConstructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        FullConstructor.__init__(self)
        Resolver.__init__(self)

class SafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)

class Loader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)

# UnsafeLoader is the same as Loader (which is and was always unsafe on
# untrusted input). Use of either Loader or UnsafeLoader should be rare, since
# FullLoad should be able to load almost all YAML safely. Loader is left intact
# to ensure backwards compatibility.
class UnsafeLoader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)


# Loaders paired with `NoSexagesimalResolver`: colon-separated YAML 1.1
# sexagesimal scalars (e.g. `1:30`) are kept as verbatim strings instead of
# being converted to base-60 integers or floats, matching the YAML 1.2 Core
# Schema.  All other implicit resolution and construction behavior is inherited
# unchanged from the corresponding default loader.
#
# These are pure-Python loaders: the libyaml-based C loaders resolve implicit
# tags inside the C extension and are not affected by NoSexagesimalResolver.
class SafeLoaderNoSexagesimal(
        Reader, Scanner, Parser, Composer, SafeConstructor, NoSexagesimalResolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        NoSexagesimalResolver.__init__(self)

class FullLoaderNoSexagesimal(
        Reader, Scanner, Parser, Composer, FullConstructor, NoSexagesimalResolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        FullConstructor.__init__(self)
        NoSexagesimalResolver.__init__(self)

class UnsafeLoaderNoSexagesimal(
        Reader, Scanner, Parser, Composer, Constructor, NoSexagesimalResolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        NoSexagesimalResolver.__init__(self)

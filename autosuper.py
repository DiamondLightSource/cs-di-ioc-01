# Meta-class to implement __super attribute in all subclasses.  To use this
# define the metaclass of the appropriate base class to be autosuper thus:
#
#     class A:
#         __metaclass__ = _autosuper_meta
#
# Then in any sub-class of A the __super attribute can be used instead of
# writing super(cls, name) thus:
#
#     class B(A):
#         def __init__(self):
#             self.__super.__init__()
#             # instead of
#             # super(B, self).__init__()
#
# The point being, of course, that simply writing
#             A.__init__(self)
# will not properly interact with calling order in the presence of multiple
# inheritance: it may be necessary to call a sibling of B instead of A at
# this point!
#
# Note that this trick does not work properly if a) the same class name
# appears more than once in the class hierarchy, and b) if the class name is
# changed after it has been constructed.  The class can be renamed during
# construction by setting the TrueName attribute.
#
#
# This meta class also supports the __init_meta__ method: if this method is
# present in the dictionary of the class it will be called after completing
# initialisation of the class.
#
# For any class with _autosuper_meta as metaclass if a method
#     __init_meta__(cls, subclass)
# is defined then it will be called when the class is declared (with subclass
# set to False) and will be called every time the class is subclassed with
# subclass set to True.
#
# This class definition is taken from
#   http://www.python.org/2.2.3/descrintro.html#metaclass_examples
class _autosuper_meta(type):
    __super = property(lambda subcls: super(_autosuper_meta, subcls))

    def __init__(cls, name, bases, dict):
        cls.__super.__init__(name, bases, dict)

        super_name = '_%s__super' % name.lstrip('_')
        assert not hasattr(cls, super_name), \
            'Can\'t set super_name on class %s, name conflict' % name
        setattr(cls, super_name, super(cls))


## Class that can be subclassed to inherit autosuper behaviour.
#
# All subclasses of this class share an attribute __super which allows
# self.__super to be used rather than super(Class, self).
class autosuper(object):
    __metaclass__ = _autosuper_meta

    def __new__(cls, *args, **kargs):
        assert super(autosuper, cls).__init__ == object.__init__, \
            'Broken inheritance hierarchy?'
        return object.__new__(cls)

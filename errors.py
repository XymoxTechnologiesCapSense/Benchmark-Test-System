

class Error(Exception):
    """
    base class for other exceptions
    """
    pass

########################################################
#
#        \          SORRY            /
#         \                         /
#          \    This page does     /
#           ]   not exist yet.    [    ,'|
#           ]                     [   /  |
#           ]___               ___[ ,'   |
#           ]  ]\             /[  [ |:   |
#           ]  ] \           / [  [ |:   |
#           ]  ]  ]         [  [  [ |:   |
#           ]  ]  ]__     __[  [  [ |:   |
#           ]  ]  ] ]\ _ /[ [  [  [ |:   |
#           ]  ]  ] ] (#) [ [  [  [ :===='
#           ]  ]  ]_].nHn.[_[  [  [
#           ]  ]  ]  HHHHH. [  [  [
#           ]  ] /   `HH("N  \ [  [
#           ]__]/     HHH  "  \[__[
#           ]         NNN         [
#           ]         N/"         [
#           ]         N H         [
#          /          N            \
#         /           q,            \
#        /                           \
###################################################

class InvalidInput(Error):
    """
    raised when input is invalid
    """

    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class InvalidAxes(Error):
    """
    raised when calibrating axes and the axes are invalid
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class NoDeviceError(Error):
    """
    Error raised when connection with the touch controller can not be made

    Due to the nature of how the __init__ method is used for the mainframe class,
    the program is force closed whenever this is called to make sure a new
    instance of the touch controller is given to the program
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class NoInputFromController(Error):
    """
    raised when no input was received from controller
    when input was expected
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class ReadFailError(Error):

    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class ZeroIndexInvalid(Error):
    """
    raised when the 0 index of the return message from the board is a non-zero integer
    when the 0th index of any return message is a non-zero integer, it means that
    some form of an error occurred-- rendering the data invalid
    To fix this I typically would just reset the board, the error would go away after that.

    If that doesn't work for you, well.. good luck!
            --    -^
           (O) | (O)
               '>
          ( _______ )
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class BadINSUNITS(Error):

    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class NotOriented(Error):
    """
    Raised when some goofy lad tries to run a test without calibrating the screen first
          \V/    /^\
          (U) \ (U)
               \,
               _')
         *^\_______/^*
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)


class SaveError(Error):
    """
    Raised when a save issue occurs trying to save a file to excel
    """
    def __init__(self, msg: str):
        self._message = msg
        super().__init__(self._message)

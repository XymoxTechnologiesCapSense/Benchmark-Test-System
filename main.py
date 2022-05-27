###########################################
#                                         #
# Touchscreen Testing Verification        #
# Author: Mitchell Allen                  #
# Date: 6/1/2021                          #
# Version 1.3                             #
#                                         #
###########################################


from MainFrame import *

def main():
    """
    main loop for the Touschscreen Verification Program
    :return: N/A
    """
    app = App(False)
    MainFrame(None, "Touchscreen Verification")
    app.MainLoop()


if __name__ == '__main__':
    main()


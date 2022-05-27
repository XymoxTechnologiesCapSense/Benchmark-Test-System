import array
import time

import numpy as np
import usb.core
import usb.backend.libusb1
import usb.util
import usb.control

import errors
from DXFReader import Point
from errors import *
import pdb

#######################################
# LIBRARY GRAVEYARD:
#
# import i2cflash
# from pyftdi.ftdi import Ftdi
# from smbus import SMBus
# import re
# import subprocess
# from pyhidapi import hid_open
# import hid
# from pyhidapi import hid_open
# import pyhidapi
# import hidapi
######################################

# If you are getting No backend error or device not found error, use this website.
# use the inf-wizard.exe to create a driver for the usb
# NOTE: RUN inf-wizard.exe AS AN ADMIN, BECAUSE I JUST SPENT AN HOUR BEING STUCK
# ONLY TO FIND THAT'S ALL I NEEDED TO DO TO FIX MY PROBLEM
# libusb-win32:
# https://sourceforge.net/projects/libusb-win32/files/libusb-win32-releases/1.2.6.0/

# REPORT IDS:
# 0x06: Object Protocol (OBP) command and response
# 0x01: Touch Report
# 0x02: Maximum Touches (Surface Contacts) report
# 0x05: Touch Hardware Quality Assurance (THQA) report

# MESSAGE FORMAT:
# 0: Rpt Id     -- Report ID (see notes)
# 1: command ID --
# 2: NumWx      -- Number of bytes to write
# 3: NumRx      -- Number of bytes to read
# 4: Addr 0     -- Mem address (least significant byte)
# 5: Addr 1     -- Mem address (most significant byte)
# 6->11: Data n -- Bytes of data to be written (if write and present)
#                  note: data given beyond what index 1 signals will be ignored

# RESPONSE FORMAT:
# 0: Rpt ID     -- report ID (see notes)
# 1: Status     -- indicates result of command
#                  0x00 = read and write complete; read data returned
#                  0x04 = write completed; no read data requested
# 2: NumRx      -- number of bytes read (in case of read), same value as
# 3-14: Data n  -- Data bytes read from memory map

# EXAMPLE 4-byte read message starting at address 0x1234:
# [0x06, 0x51, 0x02, 0x04, 0x34, 0x12]
# 0: report ID
# 1: Command ID
# 2: Number of bytes to write (NOTE: THIS IS A READ OPERATION,


# touch events and their associated meaning
ATMEL_TOUCH_EVENTS = {0: "NO EVENT", 1: "MOVE", 2: "UNSUP", 3: "SUP", 4: "DOWN",
                      5: "UP", 6: "UNSUPSUP", 7: "UNSUPUP", 8: "DOWNSUP", 9: "DOWNUP"}


# Dictionary for objects and their associated IDs
ATMEL_OBJECTS_TO_IDS = {'T6': [1], 'T68': [2], 'T15': [3], 'T19': [4], 'T25': [5], 'T46': [6], 'T56': [7],
                        'T61': [8, 9, 10, 11, 12, 13], 'T65': [14, 15, 16],
                        'T70': [17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36],
                        'T72': [37], 'T80': [38], 'T93': [39], 'T97': [40, 41, 42, 43], 'T99': [44, 45, 46, 47],
                        'T100': [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65],
                        'T108': [66], 'T109': [67], 'T112': [68], 'T115': [69]}


# Dictionary of IDs and their associated object
ATMEL_IDS_TO_OBJECTS = {1: 'T6', 2: 'T68', 3: 'T15', 4: 'T19', 5: 'T25', 6: 'T46', 7: 'T56', 8: 'T61', 9: 'T61',
                        10: 'T61', 11: 'T61', 12: 'T61', 13: 'T61', 14: 'T65', 15: 'T65', 16: 'T65', 17: 'T70',
                        18: 'T70', 19: 'T70', 20: 'T70', 21: 'T70', 22: 'T70', 23: 'T70', 24: 'T70', 25: 'T70',
                        26: 'T70', 27: 'T70', 28: 'T70', 29: 'T70', 30: 'T70', 31: 'T70', 32: 'T70', 33: 'T70',
                        34: 'T70', 35: 'T70', 36: 'T70', 37: 'T72', 38: 'T80', 39: 'T97', 40: 'T97', 41: 'T97',
                        42: 'T97', 43: 'T97', 44: 'T99', 45: 'T99', 46: 'T99', 47: 'T99', 48: 'T100', 49: 'T100',
                        50: 'T100', 51: 'T100', 52: 'T100', 53: 'T100', 54: 'T100', 55: 'T100', 56: 'T100', 57: 'T100',
                        58: 'T100', 59: 'T100', 60: 'T100', 61: 'T100', 62: 'T100', 63: 'T100', 64: 'T100', 65: 'T100',
                        66: 'T108', 67: 'T109', 68: 'T112', 69: 'T115'}


Z_OFFSET = 40


def arr_to_list(arr: array) -> list:
    """
    changes a np array to a list
    :param arr: array
    :return: list of array contents
    """
    return_list = []
    for i in arr:
        return_list.append(i)
    return return_list


def binary_to_decimal(binary_string: str) -> int:
    """
    converts a binary string into an integer
    :param binary_string: input string representing a binary number
    :return: integer retrieved from binary string
    :raises: ValueError if binary_string is not a binary string
    """
    # case where binary string begins with "0b" (often times from builtin bin() function)
    if binary_string[0:2] == "0b":
        binary_string = binary_string[2:]
    binary_string = binary_string.replace(" ", "")  # remove any whitespace
    bit_value = 2 ** (len(binary_string) - 1)  # get starting bit's value
    binary_value = 0  # initialize binary value
    for bit in binary_string:
        # handle bad input strings
        if bit != '0' and bit != '1':
            raise ValueError("Invalid binary string: " + str(binary_string))
        # add value to return value if bit is 1
        if bit == '1':
            binary_value += bit_value
        bit_value /= 2  # decrement bit value
    return int(binary_value)


def twos_complement_to_decimal(bits: str) -> int:
    """
    converts a two's complement binary value to a decimal value
    :param bits: string of bits
    :return: decimal value
    """
    value = None

    if bits[0] == '1':
        value = -int(bits[0]) << len(bits) | int(bits, 2)
    elif bits[0] == '0':
        value = binary_to_decimal(bits)

    return value


def device_info(dev) -> None:
    """
    prints device info, debugging method
    :param dev: device
    :return: N/A
    """
    for cfg in dev:
        print("Configuration Value: " + str(cfg.bConfigurationValue) + '\n')
        for intf in cfg:
            print('\t Interface Num & Alternate Setting:' + str(intf.bInterfaceNumber) +
                  ',' + str(intf.bAlternateSetting) + '\n')
            for ep in intf:
                print('\t\t Endpoint Address: ' + str(ep.bEndpointAddress) + '\n')
    # INFO:
    print("Device Backend:")
    print(dev.backend)
    print("Device configurations:")
    print(dev.configurations())


class TouchController:

    def __init__(self):
        """
        creates a TouchController object, doesn't take any parameters other than self
        """
        # USB\VID_03EB&PID_6123&REV_0054
        self._controller_name = "Microchip ATMXT1066T2"
        self._ids = {"Microchip ATMXT1066T2": (0x03EB, 0x6123)}  # update this with more controllers

        # messages for atmel touch controller
        self._t5_msg = np.array([0x51, 0x02, 0x0A, 0x89, 0x01], dtype=np.uint8)
        self._t44_msg = np.array([0x51, 0x02, 0x01, 0x88, 0x01], dtype=np.uint8)
        # get the backend
        self._backend = usb.backend.libusb1.get_backend(find_library=lambda q: "libusb-1.0.dll")

        # find our self._device
        self._device = usb.core.find(idVendor=self._ids[self._controller_name][0],
                                     idProduct=self._ids[self._controller_name][1],
                                     backend=self._backend)
        # was it found?
        if self._device is None:
            raise NoDeviceError('Device not found')

        self.reset()  # reset the board on instantiation
        self._device.set_configuration()  # set the active configuration.
        try:
            t6_disable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x00], dtype=np.uint8)
            self.write_and_read(t6_disable_debug)
        except errors.ZeroIndexInvalid:
            pass

        zero_block_ans = self.write_and_read(np.array([0x51, 0x02, 0x0A, 0x00, 0x00], dtype=np.uint8))
        num_x_nodes = zero_block_ans[6]
        num_y_nodes = zero_block_ans[7]
        self._board_num_x_nodes = None
        self._board_num_y_nodes = None
        bytes_per_node = 2
        page_size = 128
        nodes_per_page = int(page_size / bytes_per_node)

        self.data_indices_atmel = dict()
        self.page_numbers_atmel = dict()
        node_number = 0
        page_number = 0
        # create dictionary containing x&y nodes as keys and their associated data index as values
        # keys are tuples in form (x, y)
        for x in range(num_x_nodes):
            for y in range(num_y_nodes):
                self.data_indices_atmel[(x, y)] = bytes_per_node * (node_number % nodes_per_page)
                self.page_numbers_atmel[(x, y)] = page_number
                node_number += 1
                if node_number % nodes_per_page == 0:
                    page_number += 1

    def clear_buffer(self) -> None:
        """
        reads all data left out of the T5 object to clear the buffer
        :return: None
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            self._clear_buffer_atmel()
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def get_orientation_coordinates(self, max_iterations=12) -> list:
        """
        gets orientation coordinates from the screen, gets the screen coordinates rather than the coordinates in mm
        :param max_iterations: maximum times to try getting coordinates
        :return: results of read_touch_point
        """
        cont = True
        msgs_to_read = 0
        iterations = 0

        # try getting input a few times
        while cont:
            msgs_to_read = self.num_messages_to_read()
            if msgs_to_read == 0:
                iterations += 1
            else:
                cont = False
            # raise NoInputFromController Exception if max iterations reached
            if iterations >= max_iterations:
                raise NoInputFromController("Scanned " + str(max_iterations) + " times, still didn't get any input"
                                                                               " from the controller.")
        return self.read_touch_point(msgs_to_read)

    def get_delta_at(self, x_node: int, y_node: int, page_size=128):
        """
        gets the delta value at a specified node crossing

        :param x_node: x node to evaluate
        :param y_node: y node to evaluate
        :param page_size: page size of the T37 object (typically 128< i'm unaware of cases where it is not 128)
        :return: twos complement calculation of the data indices representing the delta of the node crossing
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._get_delta_at_atmel(x_node, y_node, page_size)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def get_range(self, debug=False):
        """
        gets the ranges of the screen in both the X and Y direction

        :param debug: bool for developers to get output in console, remains false unless you want debug info
        :return: x range, y range
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._get_range_atmel(debug)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def get_touch_coordinate(self) -> list:
        """
        gets the current estimated input from the touch controller
        :return: current touch controllers get_touch_coordinate results
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._get_touch_coordinate_atmel()
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def get_touch_controller_type(self):
        """
        :return: name of the currently selected touch controller
        """
        return self._controller_name

    def nine_point_read(self, x: int, y: int, iterations: int, sleep_sec: float, page_size=128, debug=False) -> list:
        """
        reads 9 nodes around the input parameter nodes and returns

        EX: the (X,Y) represents the node input, and the stars are each node relative to the
        input node that are evaluated (scans a 3x3 area)

        * - * - *
        |   |   |
        *-(X,Y)-*
        |   |   |
        * - * - *

        :param x: X node to evaluate
        :param y: Y node to evaluate
        :param iterations: number of times to red deltas
        :param sleep_sec: number of seconds to sleep between each read
        :param page_size: size of the T37 page
        :param debug: bool determining if debug data is output to the console
        :return: list of deltas in their specified locations
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._t37_nine_point_read_atmel(x, y, iterations, sleep_sec, page_size, debug)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def num_messages_to_read(self) -> int:
        """
        gets the number of messages to read from the T44 object
        :return: integer representing the number of messages to read
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._t44_num_messages_to_read_atmel()
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def read_all_points(self) -> list:
        """
        reads all touch points registered in the T5 object of the maxtouch controller
        :return: list of touch points
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._read_all_points_atmel()
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def read_touch_point(self, num_messages_to_read: int, debug=False) -> list:
        """
        gets the touch point in screen units (NOT mm !!!)

        :param num_messages_to_read: number of messages to read from the T5 object
        :param debug: determines if debug output is printed (default False)
        :return: tuple of (x_val, y_val)
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._read_touch_point_atmel(num_messages_to_read, debug)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def reset(self) -> bool:
        """
        resets the touch controller
        :return: bool indicating if the reset was successful
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._reset_atmel()
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def set_touch_controller(self, controller_name: str):
        """
        sets the touch controller being used
        :param controller_name: name of the controller being used
        :return: N/A
        """
        self._controller_name = controller_name

    def twenty_five_point_read(self, x: int, y: int, iterations: int, sleep_sec: float, page_size=128,
                               debug=False) -> list:
        """
        reads 25 nodes around the input parameter nodes and returns

        EX: the (X,Y) represents the node input, and the stars are each node relative to the
        input node that are evaluated (scans a 5x5 area)

        * - * - * - * - *
        |   |   |   |   |
        * - * - * - * - *
        |   |   |   |   |
        * - *-(X,Y)-* - *
        |   |   |   |   |
        * - * - * - * - *
        |   |   |   |   |
        * - * - * - * - *

        :param x: X node to evaluate
        :param y: Y node to evaluate
        :param iterations: number of times to red deltas
        :param sleep_sec: number of seconds to sleep between each read
        :param page_size: size of the T37 page
        :param debug: bool determining if debug data is output to the console
        :return: list of deltas in their specified locations
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._t37_twenty_five_point_read_atmel(x, y, iterations, sleep_sec, page_size, debug)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    def update_number_of_nodes(self, num_x: int, num_y: int) -> None:
        """
        updates the number of nodes on the screen
        :param num_x: number of X nodes
        :param num_y: number of Y nodes
        :return: None
        """
        self._board_num_x_nodes = num_x
        self._board_num_y_nodes = num_y

    def write_and_read(self, message: np.ndarray, timeout=2000, debug=False) -> list:
        """
        writes a message to the device and handles any possible exceptions
        :param message: message to send
        :param timeout: timeout (ms)
        :param debug: bool determining if debug data is output
        :return: answer from write command in a list
        """
        if self._controller_name == "Microchip ATMXT1066T2":
            return self._write_and_read_atmel(message, timeout, debug)
        elif self._controller_name == "NEW_CONTROLLER":
            print("implement new controller method here")
        else:
            raise ValueError("Unknown touch controller: " + self._controller_name)

    ############################
    # Atmel controller methods #
    ############################

    def _clear_buffer_atmel(self):
        """
        reads all data left out of the T5 object to clear the buffer
        :return: None
        """
        msgs_to_read = 1  # initialize msgs_to_read


        while msgs_to_read:        
            msgs_to_read = self._t44_num_messages_to_read_atmel()

            if msgs_to_read:
                for i in range(msgs_to_read):
                    self.write_and_read(self._t5_msg)
                    

    def _get_delta_at_atmel(self, x_node: int, y_node: int, page_size=128):
        """
        gets the delta value at a specified node crossing

        :param x_node: x node to evaluate
        :param y_node: y node to evaluate
        :param page_size: page size of the T37 object (typically 128< i'm unaware of cases where it is not 128)
        :return: twos complement calculation of the data indices representing the delta of the node crossing
        """
        # IMPORTANT:
        # the data is organized into pages, each page contains data regarding the input signals
        # of the board in specific locations. the data is sent in order, so all data regarding the
        # first row of X is followed by all data regarding the second row of x, and so on.
        # there will likely be more possible nodes  to be sent than actual nodes on the touchscreen being
        # tested, so many 0 will follow each row's data (the default is 26 possible nodes in the X direction)

        # all_page_data = self.t37_read_all_data_DEBUG()

        data_index = self.data_indices_atmel[(x_node, y_node)]
        page_number = self.page_numbers_atmel[(x_node, y_node)]
        ans = self._t37_read_page_atmel(page_number, page_size=page_size)

        rightmost_bits = bin(ans[data_index])[2:]
        leftmost_bits = bin(ans[data_index+1] << 8)[2:]

        binary = bin(int(leftmost_bits, 2) + int(rightmost_bits, 2))[2:]

        # handle cases where the binary representation is not 16 bits in length
        if len(binary) < 16:
            zero_bits = ''
            for i in range(16 - len(binary)):
                zero_bits += '0'
            binary = zero_bits + binary

        return twos_complement_to_decimal(binary)

    def _get_range_atmel(self, debug=False):
        """
        gets the ranges of the screen in both the X and Y direction

        :param debug: bool for developers to get output in console, remains false unless you want debug info
        :return: x range, y range
        """
        # these represent the index of the return message that indicates the
        # ls and ms bytes for x and y range, respectively
        ls_x_index = 15
        ms_x_index = 16
        ls_y_index = 26
        ms_y_index = 27

        t100_message = np.array([0x51, 0x02, 0x26, 0xFC, 0x06], dtype=np.uint8)

        retry = 10

        while True:
            resp = self.write_and_read(t100_message)
            # get X range bytes
            ls_x = resp[ls_x_index]
            ms_x = resp[ms_x_index]
            shifted_ms_x = ms_x << 8  # shift most significant byte
            x_rng = shifted_ms_x + ls_x
            # get Y range bytes
            ls_y = resp[ls_y_index]
            ms_y = resp[ms_y_index]
            shifted_ms_y = ms_y << 8  # shift most significant byte
            y_rng = shifted_ms_y + ls_y

            if x_rng != 0 and y_rng != 0:
                if debug:
                    print(" RANGE: (" + str(x_rng) + ", " + str(y_rng) + ")")
                return x_rng, y_rng
            else:
                retry -= 1
                if retry <= 0:
                    raise ZeroIndexInvalid("Unable to determine range of the touch controller.")

    def _get_touch_coordinate_atmel(self) -> list:
        """
        gets the current estimated input from the touch controller
        :return: touch coordinate
        """

        cont = True
        infinite_loop_stopper = 0
        retval = None

        while cont:
            msgs_to_read = self._t44_num_messages_to_read_atmel()

            if msgs_to_read != 0:
                # raise exception of reading wrong thing if response has wacky value
                if msgs_to_read > 12:
                    raise Exception(
                        "Response read wrong thing. number of messages its wrongly going to read: " + str(msgs_to_read))
                retval = self.read_touch_point(msgs_to_read)
                if retval[0] is not None and retval[1] is not None:
                    cont = False
            else:
                infinite_loop_stopper += 1
                if infinite_loop_stopper > 100:
                    raise NoInputFromController("cannot read this touch coordinate, damn")

        return retval

    def _read_all_points_atmel(self) -> list:
        """
        reads all touch points registered in the T5 object of the maxtouch controller
        :return: list of touch points
        """
        points = list()
        y_val = x_val = None

        for i in range(self._t44_num_messages_to_read_atmel()):
            ans = self._write_and_read_atmel(self._t5_msg)
            if ans[2] != 48:
                # get X pos bytes
                ls_x = ans[4]
                ms_x = ans[5]
                shifted_ms_x = ms_x << 8  # shift most significant byte
                old_x = x_val
                x_val = shifted_ms_x + ls_x
                # get Y pos bytes
                ls_y = ans[6]
                ms_y = ans[7]
                shifted_ms_y = ms_y << 8  # shift most significant byte
                old_y = y_val
                y_val = shifted_ms_y + ls_y

                if x_val == y_val == 0 and x_val is not None and y_val is not None:
                    x_val = old_x
                    y_val = old_y
                elif x_val is not None and y_val is not None:
                    points.append(Point(x_val, y_val))

        return points

    def _read_touch_point_atmel(self, num_messages_to_read: int, debug=False) -> list:
        """
        gets the touch point in screen units (NOT mm !!!)

        :param num_messages_to_read: number of messages to read from the T5 object
        :param debug: determines if debug output is printed (default False)
        :return: tuple of (x_val, y_val)
        """

        x_val = y_val = None
        # iterate over all messages to read
        if debug:
            print("#############################################################################################")
            print("NUM MESSAGES TO READ: " + str(num_messages_to_read))
        for i in range(num_messages_to_read):
            resp = self.write_and_read(self._t5_msg)

            # check if thing is not 49 (bad number!?)
            if resp[2] == 48:
                if debug:
                    print("TOUCH REGISTERED")

            elif 49 < resp[2] < 66:  # bound 50-63 (double check max bound)
                # PAGE 80
                tch_status = '{0:08b}'.format(resp[3])

                event_bits = tch_status[4:]
                event = int(event_bits, base=2)

                # get X pos bytes
                ls_x = resp[4]
                ms_x = resp[5]
                shifted_ms_x = ms_x << 8  # shift most significant byte
                old_x = x_val
                x_val = shifted_ms_x + ls_x
                # get Y pos bytes
                ls_y = resp[6]
                ms_y = resp[7]
                shifted_ms_y = ms_y << 8  # shift most significant byte
                old_y = y_val
                y_val = shifted_ms_y + ls_y

                # pdb.set_trace()
                if x_val == y_val == 0 and x_val is not None and y_val is not None:
                    x_val = old_x
                    y_val = old_y

                if debug:
                    print("event: " + ATMEL_TOUCH_EVENTS[event])
                    print(" Coordinates: (" + str(x_val) + ", " + str(y_val) + ")")
        if debug:
            print("MAKING POINT: (" + str(x_val) + ", " + str(y_val) + ")")
        return [x_val, y_val]

    def _reset_atmel(self) -> bool:
        """
        resets the touch controller
        :return: bool indicating if the reset was successful
        """
        # t6_reset message outline:
        # 0x51 - standard first byte to send
        # 0x03 - writing 3 bytes, 2 for address, 1 for signaling a reset
        # 0x01 - needs to be non-zero (No idea why)
        # 0x94 - LS byte of address
        # 0x01 - MS byte of address
        # 0x01 - value to write to byte 0 of the T6
        t6_reset = np.array([0x51, 0x03, 0x01, 0x94, 0x01, 0x01], dtype=np.uint8)

        try:
            self._device.read(0x81, 64, 200)
        except usb.core.USBTimeoutError:
            pass

        self.write_and_read(t6_reset)
        time.sleep(.2)
    
        reset_msgs = list()
        msgs = 1
        
        while msgs:
            msgs = self._t44_num_messages_to_read_atmel()
            for i in range(msgs):
                msg = self.write_and_read(self._t5_msg)
                if msg[2] == 1:
                    reset_msgs.append(msg[3])
        
        if reset_msgs[0] != 128:
            raise Exception("Reset not properly set")        
        if reset_msgs[1] != 16:
            raise Exception("Orientation not properly set")
        if reset_msgs[2] != 0:
            raise Exception("End not properly set")
                
        return True

    def _t37_read_page_atmel(self, page_num: int, page_size=128):
        """
        reads an entire page of the t37 object

        :param page_num: page number of the T37 to read
        :param page_size: size of the page
        :return: list of data gathered from the T37 object
        """
        t6_enable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x10], dtype=np.uint8)
        t6_disable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x00], dtype=np.uint8)
        page_up = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x01], dtype=np.uint8)
        page_down = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x02], dtype=np.uint8)
        t37_read_1 = np.array([0x51, 0x02, 0x3E, 0x06, 0x01], dtype=np.uint8)
        t37_read_2 = np.array([0x51, 0x02, 0x3E, 0x44, 0x01], dtype=np.uint8)
        t37_read_3 = np.array([0x51, 0x02, 0x3E, 0x82, 0x01], dtype=np.uint8)

        self._write_and_read_atmel(t6_enable_debug)

        # iterate to page
        for i in range(page_num):
            self._write_and_read_atmel(page_up)

        ans = self._write_and_read_atmel(t37_read_1)  # get first section of data

        while ans[3] != page_num:
            # print("####### WRONG PAGE SOMEHOW ############")
            ans = self._write_and_read_atmel(t37_read_1)  # get first section of data
            if ans[3] > page_num:
                # print('CURRENT PAGE: ' + str(ans[3]) + '\nPaging down')
                self.write_and_read(page_down)
            elif ans[3] < page_num:
                # print('CURRENT PAGE: ' + str(ans[3]) + '\nPaging up')
                self.write_and_read(page_up)

        page_data = list()
        page_data.clear()

        # get all data from page

        if ans[3] != page_num:
            raise ValueError("invalid page: " + str(ans[3]))

        page_data.extend(ans[4:])  # get 60 bytes from message (page_data is now len(60) )
        ans = self._write_and_read_atmel(t37_read_2)  # get second section of data
        page_data.extend(ans[2:])  # get 62 bytes from message (page_data is now len(122) )
        ans = self._write_and_read_atmel(t37_read_3)  # get third section of data
        end_index = page_size - len(page_data) + 2  # get the end index to read from in the line below
        page_data.extend(ans[2:end_index])  # get enough bytes from message to make len(page_data) = page_size

        self._write_and_read_atmel(t6_disable_debug)

        return page_data

    def _t37_nine_point_read_atmel(self, x: int, y: int, iterations: int, sleep_sec: float, page_size=128,
                                   debug=False) -> list:
        """
        reads 9 nodes around the input parameter nodes and returns

        EX: the (X,Y) represents the node input, and the stars are each node relative to the
        input node that are evaluated (scans a 3x3 area)

        * - * - *
        |   |   |
        *-(X,Y)-*
        |   |   |
        * - * - *

        :param x: X node to evaluate
        :param y: Y node to evaluate
        :param iterations: number of times to red deltas
        :param sleep_sec: number of seconds to sleep between each read
        :param page_size: size of the T37 page
        :param debug: bool determining if debug data is output to the console
        :return: list of deltas in their specified locations
        """
        # initialize messages
        t6_enable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x10], dtype=np.uint8)
        t6_disable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x00], dtype=np.uint8)
        page_up = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x01], dtype=np.uint8)
        page_down = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x02], dtype=np.uint8)
        t37_read_1 = np.array([0x51, 0x02, 0x3E, 0x06, 0x01], dtype=np.uint8)
        t37_read_2 = np.array([0x51, 0x02, 0x3E, 0x44, 0x01], dtype=np.uint8)
        t37_read_3 = np.array([0x51, 0x02, 0x3E, 0x82, 0x01], dtype=np.uint8)

        # handle edge cases where 9 points would be off the screen
        if x - 1 < 0:
            if debug:
                print(str(x) + ' is too small, setting it to 1')
            x = 1  # set point to one off of 0 edge (can scan x-1 -> 0 node)
        elif x + 1 >= self._board_num_x_nodes:
            if debug:
                print(str(x) + ' is too big, setting it to ' + str(self._board_num_x_nodes - 2))
            x = self._board_num_x_nodes - 2
        if y - 1 < 0:
            if debug:
                print(str(y) + ' is too small, setting it to 1')
            y = 1  # set point to one off of 0 edge (can scan y-1 -> 0 node)
        elif y + 1 >= self._board_num_y_nodes:
            if debug:
                print(str(y) + ' is too big, setting it to ' + str(self._board_num_y_nodes - 2))
            y = self._board_num_y_nodes - 2

        # create list of 9 tuples indicating which points to read
        nodes = [(x-1, y-1), (x, y-1), (x+1, y-1),
                 (x-1, y),   (x, y),   (x+1, y),
                 (x-1, y+1), (x, y+1), (x+1, y+1)]

        # create list of lists containing the deltas from each node connection
        ret_deltas = [list() for _ in range(9)]

        # run iteration amount of times
        for i in range(iterations):
            self.write_and_read(t6_enable_debug)
            # iterate over each node to scan
            ret_deltas_index = 0
            for node in nodes:
                page_num = self.page_numbers_atmel[node]  # get the page number node is on
                data_index = self.data_indices_atmel[node]  # get the data index of the node
                page_data = list()  # initialize the list for page data
                ans = self.write_and_read(t37_read_1)  # read first bit of the page

                # while loops iterates to the correct page
                while ans[3] != page_num:
                    ans = self.write_and_read(t37_read_1)  # get first section of data
                    if ans[3] > page_num:
                        self.write_and_read(page_down)
                    elif ans[3] < page_num:
                        self.write_and_read(page_up)

                page_data.extend(ans[4:])  # get 60 bytes from message (page_data is now len(60) )
                ans = self.write_and_read(t37_read_2)  # get second section of data
                page_data.extend(ans[2:])  # get 62 bytes from message (page_data is now len(122) )
                ans = self.write_and_read(t37_read_3)  # get third section of data
                end_index = page_size - len(page_data) + 2  # get the end index to read from in the line below
                page_data.extend(ans[2:end_index])  # get enough bytes from message to make len(page_data) = page_size

                # block gets the 16 bits and creates a binary value from them
                rightmost_bits = bin(page_data[data_index])[2:]
                leftmost_bits = bin(page_data[data_index + 1] << 8)[2:]
                binary = bin(int(leftmost_bits, 2) + int(rightmost_bits, 2))[2:]

                # handle cases where the binary representation is not 16 bits in length
                if len(binary) < 16:
                    zero_bits = ''
                    for _ in range(16 - len(binary)):
                        zero_bits += '0'
                    binary = zero_bits + binary

                # do the twos complement of the binary value (if neg)
                twos_comp = twos_complement_to_decimal(binary)
                ret_deltas[ret_deltas_index].append(twos_comp)  # save delta value
                ret_deltas_index += 1  # iterate deltas index for appending to the list
            self.write_and_read(t6_disable_debug)  # disable debug after getting all 9 point's data
            time.sleep(sleep_sec)
        return ret_deltas  # return list of 9 lists containing deltas for each respective point

    def _t37_twenty_five_point_read_atmel(self, x: int, y: int, iterations: int, sleep_sec: float, page_size=128,
                                          debug=False):
        """
        reads 25 nodes around the input parameter nodes and returns

        EX: the (X,Y) represents the node input, and the stars are each node relative to the
        input node that are evaluated (scans a 5x5 area)

        * - * - * - * - *
        |   |   |   |   |
        * - * - * - * - *
        |   |   |   |   |
        * - *-(X,Y)-* - *
        |   |   |   |   |
        * - * - * - * - *
        |   |   |   |   |
        * - * - * - * - *

        :param x: X node to evaluate
        :param y: Y node to evaluate
        :param iterations: number of times to red deltas
        :param sleep_sec: number of seconds to sleep between each read
        :param page_size: size of the T37 page
        :param debug: bool determining if debug data is output to the console
        :return: list of deltas in their specified locations
        """
        # initialize messages
        t6_enable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x10], dtype=np.uint8)
        t6_disable_debug = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x00], dtype=np.uint8)
        page_up = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x01], dtype=np.uint8)
        page_down = np.array([0x51, 0x03, 0x01, 0x99, 0x01, 0x02], dtype=np.uint8)
        t37_read_1 = np.array([0x51, 0x02, 0x3E, 0x06, 0x01], dtype=np.uint8)
        t37_read_2 = np.array([0x51, 0x02, 0x3E, 0x44, 0x01], dtype=np.uint8)
        t37_read_3 = np.array([0x51, 0x02, 0x3E, 0x82, 0x01], dtype=np.uint8)

        # handle edge cases where 9 points would be off the screen
        if x - 2 < 0:
            if debug:
                print(str(x) + ' is too small, setting it to 2')
            x = 2  # set point to one off of 0 edge (can scan x-1 -> 0 node)
        elif x + 2 >= self._board_num_x_nodes:
            if debug:
                print(str(x) + ' is too big, setting it to ' + str(self._board_num_x_nodes - 3))
            x = self._board_num_x_nodes - 3
        if y - 2 < 0:
            if debug:
                print(str(y) + ' is too small, setting it to 2')
            y = 2  # set point to one off of 0 edge (can scan y-1 -> 0 node)
        elif y + 2 >= self._board_num_y_nodes:
            if debug:
                print(str(y) + ' is too big, setting it to ' + str(self._board_num_y_nodes - 3))
            y = self._board_num_y_nodes - 3

        # create list of 25 tuples indicating which points to read
        nodes = [(x - 2, y - 2), (x - 1, y - 2), (x, y - 2), (x + 1, y - 2), (x + 2, y - 2),
                 (x - 2, y - 1), (x - 1, y - 1), (x, y - 1), (x + 1, y - 1), (x + 2, y - 1),
                 (x - 2, y),     (x - 1, y),     (x, y),     (x + 1, y),     (x + 2, y),
                 (x - 2, y + 1), (x - 1, y + 1), (x, y + 1), (x + 1, y + 1), (x + 2, y + 1),
                 (x - 2, y + 2), (x - 1, y + 2), (x, y + 2), (x + 1, y + 2), (x + 2, y + 2)]

        # create list of lists containing the deltas from each node connection
        ret_deltas = [list() for _ in range(25)]

        # run iteration amount of times
        for i in range(iterations):
            self.write_and_read(t6_enable_debug)
            # iterate over each node to scan
            ret_deltas_index = 0
            for node in nodes:
                page_num = self.page_numbers_atmel[node]  # get the page number node is on
                data_index = self.data_indices_atmel[node]  # get the data index of the node
                page_data = list()  # initialize the list for page data
                ans = self.write_and_read(t37_read_1)  # read first bit of the page

                # while loops iterates to the correct page
                while ans[3] != page_num:
                    ans = self.write_and_read(t37_read_1)  # get first section of data
                    if ans[3] > page_num:
                        self.write_and_read(page_down)
                    elif ans[3] < page_num:
                        self.write_and_read(page_up)

                page_data.extend(ans[4:])  # get 60 bytes from message (page_data is now len(60) )
                ans = self.write_and_read(t37_read_2)  # get second section of data
                page_data.extend(ans[2:])  # get 62 bytes from message (page_data is now len(122) )
                ans = self.write_and_read(t37_read_3)  # get third section of data
                end_index = page_size - len(page_data) + 2  # get the end index to read from in the line below
                page_data.extend(ans[2:end_index])  # get enough bytes from message to make len(page_data) = page_size

                # block gets the 16 bits and creates a binary value from them
                rightmost_bits = bin(page_data[data_index])[2:]
                leftmost_bits = bin(page_data[data_index + 1] << 8)[2:]
                binary = bin(int(leftmost_bits, 2) + int(rightmost_bits, 2))[2:]

                # handle cases where the binary representation is not 16 bits in length
                if len(binary) < 16:
                    zero_bits = ''
                    for _ in range(16 - len(binary)):
                        zero_bits += '0'
                    binary = zero_bits + binary

                # do the twos complement of the binary value (if neg)
                twos_comp = twos_complement_to_decimal(binary)
                ret_deltas[ret_deltas_index].append(twos_comp)  # save delta value
                ret_deltas_index += 1  # iterate deltas index for appending to the list
            self.write_and_read(t6_disable_debug)  # disable debug after getting all 9 point's data
            time.sleep(sleep_sec)
        return ret_deltas  # return list of 9 lists containing deltas for each respective point

    def _t44_num_messages_to_read_atmel(self) -> int:
        """
        gets the number of messages to read from the T44 object
        :return: integer representing the number of messages to read
        """
        whole_ans = self.write_and_read(self._t44_msg, 5000, debug=True)
        ans = whole_ans[2]
        return ans

    def _write_and_read_atmel(self, message: np.ndarray, timeout=2000, debug=False) -> list:
        """
        writes a message to the device and handles any possible exceptions
        :param message: message to send
        :param timeout: timeout (ms)
        :param debug: bool determining if debug data is output
        :return: answer from write command in a list
        """

        self._device.write(0x02, message, timeout)
        ans = arr_to_list(self._device.read(0x81, 64, timeout))
        if ans[0] != 0 and ans[0] != 4:
            if debug:
                print("BAD 0 INDEX: " + str(ans[0]))
            raise ZeroIndexInvalid("Index 0 of the response message is " + str(ans[0]))
        return ans

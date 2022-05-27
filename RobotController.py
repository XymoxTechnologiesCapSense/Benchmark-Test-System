###########################################
#                                         #
# Touchscreen Testing Verification        #
# Author: Mitchell Allen                  #
# Date: 6/1/2021                          #
# Revision: 1                             #
#                                         #
###########################################

import sys
import glob
import time
import math

import serial

# from TouchController import *

# NOTE: This program is designed for usage with a FISNAR F4300N
# If you intend on using an alternative machine, change the
# command lines in the methods that communicate with the robot
# [ so any case where self._serial_port.write() is called ]

# SYSTEM SPECIFICATIONS:
# these are the ABSOLUTE limits on the machine (for F4300N)
# change these for new machines to their absolute limits
# Units: mm
MAX_X = 300
MAX_Y = 300
MAX_Z = 100

# Maximum speeds of the arm in each direction
# Units: mm/sec
MAX_SPEED_XY = 800
MAX_SPEED_Z = 320


def get_index_of_value(ls: list, val):
    """
    gets the index of a given value in a list.
    If multiple copies of val are present in the list, returns the earliest copy
    of val.

    :param ls: list being evaluated
    :param val: value being checked
    :return: integer representing the index of the value
             returns -1 if value is not in list
    """

    for idx in range(len(ls)):
        if ls[idx] == val:
            return idx
    return -1


def serial_ports():
    """ Gets a list of all potential serial ports

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def validate_coordinates(x: float, y: float, z: float):
    """
    ensures that the coordinates passed in are valid (greater than 0)
    :param x: X coordinate
    :param y: Y coordinate
    :param z: Z coordinate
    :return: bool determining if a coordinate is valid
    """
    #ADD or less than max?
    if x < 0 or y < 0 or z < 0:
        return False
    return True


class RobotController:
    """
    Class for controlling the robot arm in 3D space.

    abstracted to send specific messages out the serial port depending on the currently selected robot.
    """

    def __init__(self):
        """
        constructor for a robotcontroller
        """

        self._current_robot = "Fisnar F4300N"

        self._is_oriented = False

        # initialize variables
        self._y_offset = 0
        self._x_offset = 0
        self._z_start = 20

        self._serial_port = serial.Serial(timeout=5)
        self._serial_port.baudrate = 115200
        self._serial_port.timeout = 1
        self._valid_ports = serial_ports()

        if self._valid_ports:
            self._serial_port.port = self._valid_ports[0]
            self._serial_port.open()  # open serial port
            self._port_num = 0

    def set_robot(self, robot_name: str):
        """
        sets the currently used hardware
        :param robot_name: name of the hardware being used
        :return: N/A
        """
        self._current_robot = robot_name

    def get_move_function(self):
        """
        returns the move function from the robotcontroller
        :return:
        """
        return self.move

    def get_valid_ports(self):
        """
        :return: list of all names of the valid ports
        """
        return self._valid_ports

    def set_orientation_status(self, cal: bool):
        """
        sets the orientation status
        :param cal: orientation status
        :return: N/A
        """
        self._is_oriented = cal

    def get_offsets(self):
        """
        :return: x offset, y offset
        """
        return self._x_offset, self._y_offset

    def is_oriented(self):
        """
        :return: state of orientation
        """
        return self._is_oriented

    def set_com_port(self, port_idx):
        """
        sets the com port given the index of the com port
        :param port_idx: index of the port in the list of valid ports
        :return: name of the new port being used
        """
        self._serial_port.close()
        self._port_num = port_idx
        self._serial_port.port = self._valid_ports[self._port_num]
        self._serial_port.open()
        return self._valid_ports[self._port_num]

    def switch_com_port(self) -> str:
        """
        switches between available com ports. This method iterates through a list
        to get the port.
        :return: port name that it is now connected to
        """
        self._serial_port.close()  # close connection to previous port
        # check if next port to connect to exceeds the number of ports
        if self._port_num + 1 >= len(self._valid_ports):
            self._serial_port.port = self._valid_ports[0]
            self._port_num = 0
            self._serial_port.open()
        else:
            # connect to next potential port
            self._port_num += 1
            self._serial_port.port = self._valid_ports[self._port_num]
            self._serial_port.open()

        return self._valid_ports[self._port_num]

    def get_current_com_port(self):
        """
        :return: name of the currently used COM port
        """
        return self._valid_ports[self._port_num]

    def get_current_x_coord(self):
        """
        gets the current X coordinate of the robot
        :return: X coordinate of the robot
        """
        x, y, z = self.get_current_coords()
        if validate_coordinates(x, y, z):
            return x
        return -1

    def get_current_y_coord(self):
        """
        gets the current Y coordinate of the robot
        :return: Y coordinate of the robot
        """
        x, y, z = self.get_current_coords()
        if validate_coordinates(x, y, z):
            return y
        return -1

    def get_current_z_coord(self):
        """
        gets the current Z coordinate of the robot
        :return: Z coordinate of the robot
        """
        x, y, z = self.get_current_coords()
        if validate_coordinates(x, y, z):
            return z
        return -1

    def wait_for_move(self, goal_x: float, goal_y: float, goal_z: float, timeout=15):
        """
        waits for a move by constantly reading the position of the robot while its moving
        :param goal_x: goal position's x coordinate
        :param goal_y: goal position's y coordinate
        :param goal_z: goal position's z coordinate
        :param timeout: timeout (ms) to wait before raising an exception
        :return: True if the move is completed
        """
        # handle cases where the expected move is outside of the range of the robot
        if goal_x > MAX_X or goal_y > MAX_Y or goal_z > MAX_Z:
            return True
        elif goal_x < 0 or goal_y < 0 or goal_z < 0:
            return True
        x, y, z = self.get_current_coords()  # get coordinates to check initially
        start_time = time.time_ns()
        # this while loop checks if the current coordinates are within a 2 mm range of the actual needed position
        while not goal_x - 1 < x < goal_x + 1 or not goal_y - 1 < y < goal_y + 1 or not goal_z - 1 < z < goal_z + 1:
            try:
                x, y, z = self.get_current_coords()
            except TypeError:
                raise TimeoutError("Could not communicate with the robot.")
            # handle timeouts where robot doesn't move in time
            if time.time_ns() - start_time > timeout * 1e9:
                raise TimeoutError("Robot movement exceeded timeout of " + str(timeout) + " seconds.")
        return True

    ########################
    # SERIAL.WRITE METHODS #
    ########################
    #
    # These methods specifically utilize the serial port to communicate with the robot.
    # For robots besides the FISNAR, developers will want to alter these methods to correspond to the
    # messages they expect to do the required action
    #

    def move(self, x: float, y: float, z: float, is_relative=False, is_continuous=True):
        """
        Moves the robot to a specified location based on the current robot being used
        :param x: x coordinate
        :param y: y coordinate
        :param z: z coordinate
        :param is_continuous:
        :param is_relative: signals if the move being made is relative to the robot's current position
        :return: true if it was able to move, false otherwise
        """
        if self._current_robot == "Fisnar F4300N":
            return self._move_fisnar(x, y, z, is_relative, is_continuous)
        else:  # If you want more robots to be moved, add an elif statement here
            raise ValueError("Unknown robot being used: " + self._current_robot)

    def move_home(self, timeout=12):
        """
        Move the robot to it's "home" position (0,0,0) based on the current robot being used
        :return: True is move is made, false otherwise
        """

        if self._current_robot == "Fisnar F4300N":
            self._move_home_fisnar(timeout)
        else:  # If you want more robots to be moved, add an elif statement here
            raise ValueError("Unknown robot being used: " + self._current_robot)

    def get_current_coords(self):
        """
        Gets the coordinates of the machine as floats
        :return: x, y, and z coordinates (in that order) of the robot
        """
        if self._current_robot == "Fisnar F4300N":
            x, y, z = self._get_current_coords_fisnar()
            return x, y, z
        else:  # If you want more robots to be moved, add an elif statement here
            raise ValueError("Unknown robot being used: " + self._current_robot)

    def set_speed_point_to_point(self, speed: float):
        """
        Sets the speed of the robot
        For the fisnar, the speed is in mm/sec
        speed may be different with other robots
        :param speed: speed to set the robot to
        :return: N/A
        """
        if self._current_robot == "Fisnar F4300N":
            self._set_speed_point_to_point_fisnar(speed)
        else:  # If you want more robots to be moved, add an elif statement here
            raise ValueError("Unknown robot being used: " + self._current_robot)

    ##########################
    # FISNAR related methods #
    ##########################

    def _move_fisnar(self, x: float, y: float, z: float, is_relative=False, is_continuous=True):
        """
        THIS METHOD USES SELF._SERIAL_PORT.WRITE

        Moves the robot to a specified location
        :param x: x coordinate
        :param y: y coordinate
        :param z: z coordinate
        :param is_continuous:
        :param is_relative: signals if the move being made is relative to the robot's current position
        :return: true if it was able to move, false otherwise
        """
        # get values as strings (max of 5 characters in the string)
        cord_x = str(x) if len(str(x)) <= 5 else str(x)[0:5]
        cord_y = str(y) if len(str(y)) <= 5 else str(y)[0:5]
        cord_z = str(z) if len(str(z)) <= 5 else str(z)[0:5]
        # do not tell the robot to go beyond it's limit
        cord_x = str(MAX_X) if x > MAX_X else cord_x
        cord_y = str(MAX_Y) if y > MAX_Y else cord_y
        cord_z = str(MAX_Z) if z > MAX_Z else cord_z

        if not is_relative:
            cord_x = str(0) if x < 0 else cord_x
            cord_y = str(0) if y < 0 else cord_y
            cord_z = str(0) if z < 0 else cord_z
        else:
            # executes if is_relative=True
            x, y, z = self.get_current_coords()
            time_ns = time.time_ns()
            while float(x) == -1 or y == -1 or z == -1:
                x, y, z = self.get_current_coords()
                if time.time_ns() - time_ns > 10E9:
                    raise TimeoutError("Reading coordinates exceeded timeout.")
            x += float(cord_x)
            y += float(cord_y)
            z += float(cord_z)

        # this if statement is entered if the movement is supposed to be continuous
        # (as in, one straight, continuous line from the current position to the new position)
        if is_continuous:
            # command is different if move is relative or absolute
            if is_relative:
                command = "LAR " + cord_x + "," + cord_y + "," + cord_z + " \r\n"
            else:
                command = "LA " + cord_x + "," + cord_y + "," + cord_z + " \r\n"
        else:  # executes if move is not continuous
            if is_relative:  # executes if move is a relative move
                command = "MAR " + cord_x + "," + cord_y + "," + cord_z + " \r\n"
            else:  # executes if move is absolute
                command = "MA " + cord_x + "," + cord_y + "," + cord_z + " \r\n"

        try:
            self._serial_port.write(bytes(command, "utf-8"))
            if is_relative:  # executes if move is relative
                return self.wait_for_move(x, y, z)
            else:  # executes if not move reading and is not relative (normal absolute movement)
                return self.wait_for_move(float(cord_x), float(cord_y), float(cord_z))
        except serial.SerialException or TimeoutError:
            return False

    def _move_home_fisnar(self, timeout=12):
        """
        THIS METHOD USES SELF._SERIAL_PORT.WRITE

        Move the robot to it's "home" position (0,0,0)
        :return: True is move is made, false otherwise
        """
        try:
            self._serial_port.write(bytes("HM\r\n", "utf-8"))
            return self.wait_for_move(0, 0, 0, timeout=timeout)  # wait for move to complete before exiting method
        except serial.SerialException or TimeoutError:
            return False

    def _get_current_coords_fisnar(self):
        """
        THIS METHOD USES SELF._SERIAL_PORT.WRITE

        Gets the coordinates of the machine as floats
        :return: x, y, and z coordinates (in that order) of the robot
        """

        # Example outputs from readlines() when PA is called:
        # [b'ok\r\n', b'ok\r\n', b'ok\r\n', b'30,30,50\r\n', b'ok\r\n', b'ok\r\n']
        # [b'ok\r\n', b'ok\r\n', b'ok\r\n', b'80,90,65.3985\r\n', b'ok\r\n', b'ok\r\n']

        self._serial_port.write(bytes("PA\r\n", "utf-8"))
        output_list = self._serial_port.readlines()
        output_str = None

        for ele in output_list:
            ele_as_str = ele.decode("utf-8")
            if ele_as_str != "ok\r\n":
                output_str = ele_as_str

        if output_str is None:
            return -1, -1, -1
        else:
            try:
                ls = output_str.split(",")
                x_val = float(ls[0])
                y_val = float(ls[1])
                z_val = float(ls[2])
                return x_val, y_val, z_val
            except ValueError:
                return None

    def _set_speed_point_to_point_fisnar(self, speed: float):
        """
        THIS METHOD USES SELF._SERIAL_PORT.WRITE

        Sets the speed of the robot
        For the fisnar, the speed is in mm/sec
        speed may be different with other robots
        :param speed: speed to set the robot to
        :return: N/A
        """
        self._serial_port.write(bytes("SP " + str(speed) + "\r\n", "utf-8"))

##
#
##
"""
Below are the Unit codes for modelspace.units

0 Unitless
1 Inches, units.IN
2 Feet, units.FT
3 Miles, units.MI
4 Millimeters, units.MM
5 Centimeters, units.CM
6 Meters, units.M
7 Kilometers, units.KM
8 Microinches
9 Mils
10 Yards, units.YD
11 Angstroms
12 Nanometers
13 Microns
14 Decimeters, units.DM
15 Decameters
16 Hectometers
17 Gigameters
18 Astronomical units
19 Light years
20 Parsecs
21 US Survey Feet
22 US Survey Inch
23 US Survey Yard
24 US Survey Mile
"""

# HELP:
# for e in msp:
        #     if e.dxftype() == 'CIRCLE':
        #         self.print_entity(e)
# def print_entity(self, e):
    #     print("CIRCLE on layer: %s" % e.dxf.layer)
    #     # print("start point: %s" % e.dxf.start)
    #     # print("end point: %s\n" % e.dxf.end)
import math

import ezdxf as ez
import ezdxf.lldxf.const

import errors
from errors import InvalidInput


class DXFReader:
    """
    class for reading in information from a DXF file

    NOTES:
        The file must have
        - LINEARITY LAYER
            with *lines* representing the path for the robot to take
            the robot goes from the start of each line to the end of the line
            the order of the lines that are visited is based on when they are
            put into the file

        - JITTER LAYER
            with *circles* representing the touch points (the center is used)

        - ACCURACY LAYER
            with *circles* representing the touch points (the center is used)

        - SNR LAYER
            with *circles* representing the touch points (the center is used)

        - SENSOR LAYER **************IMPORTANT******************
            With a *rectangle* and a *circle* representing the active area and
            origin of the sensor, respectively

        if ANY of these requirements are not met, their respective tests
        will not be able to run, and will therefore crash the program
    """

    def __init__(self, filepath: str, offsets=None):
        """
        constructor for the DXFReader
        :param filepath: filepath of file to read in
        :param offsets: offsets of the artificial finger
        """
        if offsets is None:
            x_offset = 0
            y_offset = 0
        elif len(offsets) == 2:
            x_offset = offsets[0]
            y_offset = offsets[1]
        else:
            raise ImportError("Offsets are length 2, they are " + str(len(offsets)))
        self._current_file = ez.readfile(filepath)
        msp = self._current_file.modelspace()

        self._units = self.figure_file_units()
        self._conversion_rate = self.figure_conversion_rate()
        self._offsets = None

        # IMPORTANT:
        # when getting Y coordinates from a dxf file, they MUST be absolute values
        # with how the robot is oriented, the positive Y axis moves down (towards
        # quadrant III and IV, as opposed to going up like a standard cartesian
        # coordinate plane

        # initialize lists for edge and core sections of tests
        self._accuracy_core = list()
        self._accuracy_edge = list()
        self._jitter_core = list()
        self._jitter_edge = list()
        self._linearity_core = list()
        self._linearity_edge = list()
        self._snr_core = list()
        self._snr_edge = list()

        self._active_area = None
        self._origin = None
        lwpolyline_obj = None

        # iterate over each shape in the modelspace of the dxf file
        # only uses shapes that are in their correct layers,
        # disregards everything else
        for e in msp:
            if e.dxf.layer.upper()[:9] == 'LINEARITY':
                start_x = e.dxf.start[0]*self._conversion_rate + x_offset
                start_y = abs(e.dxf.start[1]*self._conversion_rate) + y_offset
                end_x = e.dxf.end[0]*self._conversion_rate + x_offset
                end_y = abs(e.dxf.end[1]*self._conversion_rate) + y_offset
                ln = Line(start_x, start_y, end_x, end_y)

                if e.dxf.layer.upper() == 'LINEARITY_CORE':
                    self._linearity_core.append(ln)
                elif e.dxf.layer.upper() == 'LINEARITY_EDGE':
                    self._linearity_edge.append(ln)
                else:
                    raise ImportError("Invalid Layer Name: " + e.dxf.layer)
            elif e.dxf.layer.upper()[:6] == 'JITTER':
                point = Point(round(e.dxf.center[0]*self._conversion_rate, 2) + x_offset,
                              abs(round(e.dxf.center[1]*self._conversion_rate, 2)) + y_offset)
                if e.dxf.layer.upper() == 'JITTER_CORE':
                    self._jitter_core.append(point)
                elif e.dxf.layer.upper() == 'JITTER_EDGE':
                    self._jitter_edge.append(point)
                else:
                    raise ImportError("Invalid Layer Name: " + e.dxf.layer)
            elif e.dxf.layer.upper()[:8] == 'ACCURACY':
                point = Point(round(e.dxf.center[0] * self._conversion_rate, 2) + x_offset,
                              abs(round(e.dxf.center[1] * self._conversion_rate, 2)) + y_offset)
                if e.dxf.layer.upper() == 'ACCURACY_CORE':
                    self._accuracy_core.append(point)
                elif e.dxf.layer.upper() == 'ACCURACY_EDGE':
                    self._accuracy_edge.append(point)
                else:
                    raise ImportError("Invalid Layer Name: " + e.dxf.layer)
            elif e.dxf.layer.upper()[:3] == 'SNR':
                point = Point(round(e.dxf.center[0] * self._conversion_rate, 2) + x_offset,
                              abs(round(e.dxf.center[1] * self._conversion_rate, 2)) + y_offset)
                if e.dxf.layer.upper() == 'SNR_CORE':
                    self._snr_core.append(point)
                elif e.dxf.layer.upper() == 'SNR_EDGE':
                    self._snr_edge.append(point)
                else:
                    raise ImportError("Invalid Layer Name: " + e.dxf.layer)
            elif e.dxf.layer.upper() == 'ACTIVE_AREA' and e.dxftype() == 'LWPOLYLINE':
                # save rectangle outlining the active area for ActiveArea instantiation
                lwpolyline_obj = e
            elif e.dxf.layer.upper() == 'Y_NODE_CC':
                start_x = e.dxf.start[0] * self._conversion_rate + x_offset
                start_y = abs(e.dxf.start[1] * self._conversion_rate) + y_offset
                end_x = e.dxf.end[0] * self._conversion_rate + x_offset
                end_y = abs(e.dxf.end[1] * self._conversion_rate) + y_offset
                self._y_node_line = Line(start_x, start_y, end_x, end_y)
            elif e.dxf.layer.upper() == 'X_NODE_CC':
                start_x = e.dxf.start[0] * self._conversion_rate + x_offset
                start_y = abs(e.dxf.start[1] * self._conversion_rate) + y_offset
                end_x = e.dxf.end[0] * self._conversion_rate + x_offset
                end_y = abs(e.dxf.end[1] * self._conversion_rate) + y_offset
                self._x_node_line = Line(start_x, start_y, end_x, end_y)

        # make sure active area and origin are present
        if lwpolyline_obj is not None:
            # set up active area after reading all elements in the modelspace
            self._active_area = ActiveArea(lwpolyline_obj.get_points(),
                                           self._conversion_rate, x_offset, y_offset)
        else:
            raise ImportError("Error encountered creating active area from Sensor Layer")

        if self._x_node_line and self._y_node_line:
            self._nodal_origin = None
            self._nodal_x_direction = None
            self._nodal_y_direction = None
            x_pts = [self._x_node_line.get_start_point(), self._x_node_line.get_end_point()]
            y_pts = [self._y_node_line.get_start_point(), self._y_node_line.get_end_point()]
            # find nodal origin
            for x_pt in x_pts:
                for y_pt in y_pts:
                    if x_pt[0] == y_pt[0] and x_pt[1] == y_pt[1]:
                        self._nodal_origin = x_pt
            # find positive X direction for nodes
            for pt in x_pts:
                if pt != self._nodal_origin:
                    self._nodal_x_direction = pt
            # find positive Y direction for nodes
            for pt in y_pts:
                if pt != self._nodal_origin:
                    self._nodal_y_direction = pt
        else:
            raise ImportError("Error encountered creating active area from Sensor Layer")

    def get_active_area(self):
        """
        getter method for the active area object stored in the DXFReader
        :return:
        """
        return self._active_area

    def get_accuracy_core(self):
        """
        returns the core points to be tested for the accuracy test
        :return: list of points
        """
        return self._accuracy_core

    def get_accuracy_edge(self):
        """
        returns a list of accuracy points to be tested
        :return:
        """
        return self._accuracy_edge

    def get_jitter_core(self):
        """
        returns a list of jitter points to be tested representing the jitter core
        :return:
        """
        return self._jitter_core

    def get_jitter_edge(self):
        """
        returns a list of points representing the jitter edge points to be tested
        :return:
        """
        return self._jitter_edge

    def get_linearity_core(self):
        """
        returns a list of lines representing the linearity lines of the core to be tested
        :return:
        """
        return self._linearity_core

    def get_linearity_edge(self):
        """
        returns a list of lines representing the linearity lines to be tested
        :return:
        """
        return self._linearity_edge

    def get_snr_core(self):
        """
        returns a list of points representing SNR core points to be tested
        :return: list of points
        """
        return self._snr_core

    def get_snr_edge(self):
        """
        returns a list of points representing SNR edge points to be tested
        :return:
        """
        return self._snr_edge

    def get_origin(self):
        """
        returns the origin of the active area
        :return: Point object
        """
        if self._active_area.get_origin() is not None:
            return self._active_area.get_origin()
        else:
            raise ValueError("Origin has yet to be set.")

    def get_nodal_origin(self):
        """
        returns the origin of the nodes
        :return: Point
        """
        return self._nodal_origin

    def get_nodal_x_direction(self):
        """
        returns the endpoint of the positive X direction of the nodes
        :return:
        """
        return self._nodal_x_direction

    def get_nodal_y_direction(self):
        """
        returns the endpoint of the positive Y direction of the nodes
        :return:
        """
        return self._nodal_y_direction

    def get_units(self):
        """
        gets the units of the DXF file
        :return:
        """
        return self._units

    def get_x_node_line(self):
        """
        returns the nodal X line
        :return:
        """
        return self._x_node_line

    def get_y_node_line(self):
        """
        returns the nodal y line
        :return:
        """
        return self._y_node_line

    def figure_file_units(self):
        """
        reads from the '$INSUNITS' section of the current file to determine what units are being used
        :return: string representing the units of the file
        """
        units_dict = {0: "unitless", 1: "inches", 2: "feet", 3: "miles", 4: "millimeters", 5: "centimeters",
                      6: "meters", 7: "kilometers", 10: "yard", 14: "decimeters"}

        try:
            file_units = units_dict.get(self._current_file.header['$INSUNITS'])  # try to get units from the dictionary
        except ezdxf.lldxf.const.DXFKeyError:
            raise errors.BadINSUNITS("DXF file must specify the $INSUNITS field")
        return file_units

    def figure_conversion_rate(self):
        """
        method for taking the DXF file's units and converting it to mm for the robot to use
        :return: conversion rate from (units) to mm
        """
        if self._units.lower() == "inches":
            return 25.4
        elif self._units.lower() == "feet":
            return 304.8
        elif self._units.lower() == "miles":
            return 1.609e6
        elif self._units.lower() == "millimeters":
            return 1
        elif self._units.lower() == "centimeters":
            return 10
        elif self._units.lower() == "meters":
            return 100
        elif self._units.lower() == "kilometers":
            return 1000
        elif self._units.lower() == "yard":
            return 914.4
        elif self._units.lower() == "decimeters":
            return 100
        elif self._units.lower() == "unitless":
            raise ValueError("DXF file is unitless, please specify units.")
        else:
            raise ValueError("Invalid units for figuring conversion rate: " + self._units)

    def update_offset(self, x_offset: float, y_offset: float, is_reset=False):
        """
        updates the offset of all shapes contained in the reader
        :param x_offset: finger offset from the 0, 0 point of the robot (x direction)
        :param y_offset: finger offset from the 0, 0 point of the robot (y direction)
        :param is_reset: bool determining if you need to reset or not
        :return: N/A
        """
        if not is_reset:
            self._offsets = (x_offset, y_offset)
        # update ALL the testing points
        for pt in self._accuracy_edge:
            pt[0] += x_offset
            pt[1] += y_offset
        for pt in self._accuracy_core:
            pt[0] += x_offset
            pt[1] += y_offset
        for pt in self._jitter_edge:
            pt[0] += x_offset
            pt[1] += y_offset
        for pt in self._jitter_core:
            pt[0] += x_offset
            pt[1] += y_offset
        for pt in self._snr_edge:
            pt[0] += x_offset
            pt[1] += y_offset
        for pt in self._snr_core:
            pt[0] += x_offset
            pt[1] += y_offset
        for ln in self._linearity_edge:
            ln.update(x_offset, y_offset)
        for ln in self._linearity_core:
            ln.update(x_offset, y_offset)

        self._nodal_origin['x'] += x_offset
        self._nodal_origin['y'] += y_offset
        self._nodal_x_direction['x'] += x_offset
        self._nodal_x_direction['y'] += y_offset
        self._nodal_y_direction['x'] += x_offset
        self._nodal_y_direction['y'] += y_offset

        self._active_area.update_offset(x_offset, y_offset)

    def reset_offsets(self):
        """
        resets the offsets to be 0, 0 so uploading a new set of offsets
        doesn't skew the file to be different that it actually is
        :return:
        """
        if self._offsets:
            x_offset = -1 * self._offsets[0]
            y_offset = -1 * self._offsets[1]
            self.update_offset(x_offset, y_offset, is_reset=True)


class Point:
    """
    Class that represents a point on the screen

    Points are comprised of an X and Y component
    """

    def __init__(self, *args):
        """
        points constructor
        :param args: arguments to be passed in, should be (X, Y) coordinates
        """

        if len(args) == 2:
            x = float(args[0])
            y = float(args[1])
            self._x_coordinate = x
            self._y_coordinate = y
        else:
            raise InvalidInput("Arguments passed in are not valid for point instantiation")

    def __eq__(self, other) -> bool:
        """
        overwrites the '==' operator to see if two points are equal
        :param other:
        :return:
        """
        return type(other) == Point and self._x_coordinate == other['x'] and self._y_coordinate == other['y']

    def __getitem__(self, item):
        """
        allows users to index point objects

        Example: imagine there is a point object: point = Point(10, 20)

                 calling point['x'] will return the x component of the point
                 same with point[0]

        :param item: item used to get specified index
        :raises: KeyError if item is an invalid key to index a point
        :return: X or Y coordinate, depending on what item is
        """

        if item == 'X' or item == 'x':
            return self._x_coordinate
        elif item == 'Y' or item == 'y':
            return self._y_coordinate
        elif item == 0:
            return self._x_coordinate
        elif item == 1:
            return self._y_coordinate
        else:
            raise KeyError("Invalid Input: " + str(item))

    def __setitem__(self, key, value: float):
        """
        allows users to set the x and y coordinates of a point

        Example: point = Point(10, 20)
                 print(str(point))
                 # output:
                 # (10, 20)

                 point['x'] = 75
                 print(str(point))
                 # output:
                 # (75, 20)

        :param key: key to index coordinate
        :param value: value to change coordinate to (must be a number)
        :return: nothing
        """

        if value.__class__ is not float and value.__class__ is not int:
            raise ValueError("Point value is not a number.")

        if key == 'X' or key == 'x':
            self._x_coordinate = value
        elif key == 'Y' or key == 'y':
            self._y_coordinate = value
        elif key == 0:
            self._x_coordinate = value
        elif key == 1:
            self._y_coordinate = value
        else:
            raise KeyError("Invalid Key: " + str(key))

    def __len__(self):
        """
        overrides length built-in
        :return: 2, because points have 2 coordinates associated with them
        """
        return 2  # two items stored in object (x and y)

    def __str__(self):
        """
        returns point as a string representation
        :return: '(x, y)'
        """
        return "(" + str(round(self._x_coordinate, 2)) + ", " + str(round(self._y_coordinate, 2)) + ")"


class ActiveArea:
    """
    Defines the active area of the screen
    """

    def __init__(self, points: list, conversion_rate: float, x_offset: float, y_offset: float, origin=None):
        """
        creates an active area for use by the Robot Controller

        :param points: 4 corners of the active area in a list
        :param origin: origin (0, 0) point of sensor
        :param conversion_rate: convert dxf units into units usable by the robot
        :param x_offset: finger offset from the 0, 0 point of the robot (x direction)
        :param y_offset: finger offset from the 0, 0 point of the robot (y direction)
        """
        self._conversion_rate = conversion_rate

        if len(points) != 4:
            raise ImportError("Active area does not have 4 points")

        self._points = list()
        self._origin = None
        scaled_origin = None
        # get the origin point scaled with the conversion rate and absolute values
        if origin is not None and len(origin) == 2:
            scaled_origin = Point(origin[0] * self._conversion_rate + x_offset,
                                  abs(origin[1] * self._conversion_rate - y_offset))

        origin_found = False  # initialize variable for showing that an origin was found and applied to self._origin

        # iterate over all points
        for point in points:
            # get x and y points
            x_pt = point[0] * self._conversion_rate + x_offset
            y_pt = abs(point[1] * self._conversion_rate - y_offset)
            # save origin point if one of active area points
            if scaled_origin is not None and x_pt == scaled_origin['x'] and y_pt == scaled_origin['y']:
                self._origin = scaled_origin
                if origin_found:
                    raise ImportError("Multiple origins in sensor layer, check .dxf File")
                else:
                    origin_found = True
            # save point onto active area points
            self._points.append(Point(x_pt, y_pt))

        x_coordinates = list()
        y_coordinates = list()

        base_point_found = False
        base_point = None

        for point in self._points:
            if not base_point_found:
                base_point = point
                base_point_found = True
            else:
                if round(base_point['x'], 4) == round(point['x'], 4) and \
                        round(base_point['y'], 4) != round(point['y'], 4):
                    self._height = abs(point['y'] - base_point['y'])
                elif round(base_point['x'], 4) != round(point['x'], 4) and \
                        round(base_point['y'], 4) == round(point['y'], 4):
                    self._width = abs(point['x'] - base_point['x'])

            x_coordinates.append(point['x'])
            y_coordinates.append(point['y'])

        min_x = min(x_coordinates)
        min_y = min(y_coordinates)

        # find point closest to origin
        for point in self._points:
            if point['x'] == min_x and point['y'] == min_y:
                self._point_closest_to_robot_origin = point

    def get_closest_point_to_robot_origin(self):
        """
        gets the point closest to the origin of the robot
        :return:
        """
        return self._point_closest_to_robot_origin

    def get_width(self):
        """
        gets the width of the active area (which, if facing head it head on, will be the left-right distance)
        :return:
        """
        return self._width

    def get_height(self):
        """
        gets the height of the active area (if facing, will be the up-down distance)
        :return:
        """
        return self._height

    def get_origin(self):
        """
        :return: origin of the active area
        """
        return self._origin

    def set_origin(self, origin: Point):
        """
        sets the origin of the active area
        :param origin: origin point to set
        :return: N/A
        """
        self._origin = origin

    def get_points(self):
        """
        :return: corners of the active area
        """
        return self._points

    def update_offset(self, x_offset: float, y_offset: float):
        """
        updates the offset of the finger on the active area
        :param x_offset: finger offset from the 0, 0 point of the robot (x direction)
        :param y_offset: finger offset from the 0, 0 point of the robot (y direction)
        :return: N/A
        """
        count = 0

        # iterate through all points and update the offsets of them
        for point in self._points:
            new_x = point['x'] + x_offset
            new_y = point['y'] + y_offset
            self._points[count] = Point(new_x, new_y)
            count += 1


class Line:
    """
    Lines used for the linearity tests
    """
    def __init__(self, *args):
        """
        constructor for a Line object
        :param args: either two point object, or 4 individual floats
        """
        if len(args) == 4:
            start_x = args[0]
            start_y = args[1]
            end_x = args[2]
            end_y = args[3]
        elif len(args) == 2:
            for arg in args:
                if type(arg) != Point:
                    raise ValueError("Trying to make a line object with points, but the ")
            start_x = args[0]['x']
            start_y = args[0]['y']
            end_x = args[1]['x']
            end_y = args[1]['y']
        else:
            raise ValueError

        self._start_point = Point(start_x, start_y)
        self._end_point = Point(end_x, end_y)
        self.length = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)

    def get_start_point(self):
        """
        :return: start point of line
        """
        return self._start_point

    def get_end_point(self):
        """
        :return: end point of line
        """
        return self._end_point

    def get_start_x(self):
        """
        :return: x coordinate of start point
        """
        return self._start_point['x']

    def get_start_y(self):
        """
        :return: y coordinate of start point
        """
        return self._start_point['y']

    def get_end_x(self):
        """
        :return: x coordinate of end point
        """
        return self._end_point['x']

    def get_end_y(self):
        """
        :return: y coordinate of end point
        """
        return self._end_point['y']

    def get_length(self):
        """
        returns the length of a line
        :return:
        """
        return self.length

    def update(self, x_offset: float, y_offset: float):
        """
        updates the offsets of the line points
        :param x_offset: finger offset from the 0, 0 point of the robot (x direction)
        :param y_offset: finger offset from the 0, 0 point of the robot (y direction)
        :return:
        """
        self._start_point['x'] += x_offset
        self._end_point['x'] += x_offset
        self._start_point['y'] += y_offset
        self._end_point['y'] += y_offset

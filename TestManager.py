import math
import queue
import threading
import time
import pdb

from PIL import Image
from matplotlib import pyplot as plt

import errors
from DXFReader import Line, Point, DXFReader
from ExcelSaver import ExcelSaver
from RobotController import RobotController
from TouchController import TouchController


Z_OFFSET = 30


def are_nums_close(num1, num2, closeness=100) -> bool:
    """
    determines if two numbers are close
    :param num1: first number
    :param num2: second number
    :param closeness: how close values may be
    :return: bool determining if the numbers are within the close range
    """
    return abs(num1 - num2) < closeness


def calc_jitter(touch_points: list) -> list:
    """
    calculates the jitter of the touch points
    :param touch_points: list of touch points and their data
    :return: list of jitter data
    """
    # JITTERx = max(x1 thru xn) - min(x1 thru xn)
    # JITTERy = max(y1 thru yn) - min(y1 thru yn)
    jitter_data = list()

    for test in touch_points:
        tested_point = test[0]  # save the point that was tested (0th index of test represnts location of test)
        # set up minimums and maximums with arbitrary values
        # (values allow them to certainly be replaced)
        x_max = y_max = -1
        x_min = y_min = 9e6
        for point in test:  # iterate through each point of the test
            if point is not tested_point:  # ignore the base point (where test was given)
                # calculate distances of point from the tested point
                x_distance = abs(tested_point['x'] - point['x'])
                y_distance = abs(tested_point['y'] - point['y'])

                # figure if x distance is a max or min
                if x_distance > x_max:
                    x_max = x_distance
                if x_distance < x_min:
                    x_min = x_distance
                # figure if y distance is a max or min
                if y_distance > y_max:
                    y_max = y_distance
                if y_distance < y_min:
                    y_min = y_distance

        # calculate jitter
        jitter_x = x_max - x_min
        jitter_y = y_max - y_min

        # create point data (Point, tuple[of jitter values], list of all points read)
        point_data = (tested_point, (jitter_x, jitter_y), test)
        jitter_data.append(point_data)  # append point data to return list
    return jitter_data


def calc_accuracy(touch_list: list):
    """
    calculates the accuracy of each point
    :param touch_list: [ actual_point, calculated_point1, calculated_point2, ..., calculated_pointN ]
    :return: accuracy data to be printed to excel
    """
    # Xerr = Xr - Xp
    # Yerr = Yr - Yp
    # acc = sqrt(Xerr^2 + Yerr^2)

    acc_data = []

    # iterate over each index of the touch_list
    for ls in touch_list:
        # get robot's touch coordinates
        x_robot = ls[0]['x']
        y_robot = ls[0]['y']

        # create list where first index is list of x,y coordinates, followed by accuracy values, and then errors
        point_data = [ls[0]]
        point_acc = list()
        point_err = list()
        point_loc = list()

        # iterate over all points
        for point in ls:
            if point is not ls[0]:  # if point is not the 0th index
                x_err = point['x'] - x_robot  # calculate error in the x direction
                y_err = point['y'] - y_robot  # calculate error in the y direction
                accuracy = math.sqrt(x_err ** 2 + y_err ** 2)  # calculate the total error
                point_acc.append(accuracy)  # append error to the list
                point_loc.append((point['x'], point['y']))
                point_err.append((x_err, y_err))  # append actual error values to list

        # point_data example:
        # [ (x, y), [2.3, .56, 4.89], [(x_err, y_err), (x_err, y_err), (x_err, y_err)] ]
        # [ point_object, [2.3, .56, 4.89], [(2.53, -0.52), (-1.54, 0.12), (3.68, 1.23)] ]

        # point_data[0] are the x and y coordinates the accuracy values are taken at (Point object)
        # point_data[1] are the accuracy values of a given point
        # point_data[2] are the X and Y errors of the given touch iteration
        #
        # x and y are coordinates test was given at, second list is
        # all of the accuracy values generated
        point_data.append(point_acc)
        point_data.append(point_loc)
        point_data.append(point_err)
        # acc data is comprised of multiple point data lists
        acc_data.append(point_data)

    return acc_data


def calc_linearity(core_lines_and_points: list, edge_lines_and_points: list, part_name: str, test_num: int,
                   debug=False):
    """
    takes line data and creates a graph displaying
        1) the actual lines that were drawn
        2) the values got from the touch controller
    :param test_num: the test iteration of this test
    :param core_lines_and_points: list of core lines and points to test
    :param edge_lines_and_points: list of edge lines and points to test
    :param debug: bool determining if the output of the test is print (False by default, used for development only)
    :return: core distances, edge distances, all data
    """
    max_distance = 999999999999999
    fig, ax = plt.subplots()

    core_distances = list()
    edge_distances = list()

    img_title = "Linearity Test Results For " + part_name + ", iteration " + str(test_num)
    ax.set(xlabel="X - Axis (mm)", ylabel="Y - Axis (mm)", title=img_title)

    all_points_and_lines = [core_lines_and_points, edge_lines_and_points]
    is_core = True
    # iterate over both lists (core and edge)
    for data in all_points_and_lines:
        for single_line_data in data:  # iterate over single lines of data [line, point1, point2, ...., pointN]
            start_point = None  # initialize start point
            end_point = None  # initialize end point
            for line_data in single_line_data:  # iterate over each dxf object in the single_line data
                if type(line_data) is Line:  # should only happen once for 0th index of single_line_data
                    # plot the line
                    start_point = line_data.get_start_point()
                    end_point = line_data.get_end_point()
                    ax.plot([start_point['x'], end_point['x']], [start_point['y'], end_point['y']], 'r--')
                    start_point = single_line_data[1]
                    end_point = single_line_data[-1]
                    if debug:
                        print("LINE PLOTTED:")
                        print("START: " + str(start_point))
                        print("END: " + str(end_point))
                elif type(line_data) is Point:
                    # plot each point
                    plt.plot(line_data['x'], line_data['y'], marker='o', color='black', markersize=2)
                    #########################################
                    # find perpendicular distance from line #
                    #########################################

                    # find slope m = (y2-y1)/(x2-x1)
                    top_of_fraction = end_point['y'] - start_point['y']  # (y2-y1)
                    bottom_of_fraction = end_point['x'] - start_point['x']  # (x2-x1)

                    if abs(top_of_fraction) < 0.00001:  # case 1) line is horizontal, opposite reciprocal is a vertical line
                        d = abs(round(start_point['y'] - line_data['y'], 2))
                        if d < max_distance:
                            if is_core:
                                core_distances.append(d)
                            else:
                                edge_distances.append(d)

                    elif abs(bottom_of_fraction) < 0.00001:  # case 2) line is vertical, opp. rec. is a horizontal line
                        d = abs(round(start_point['x'] - line_data['x'], 2))
                        if d < max_distance:
                            if is_core:
                                core_distances.append(d)
                            else:
                                edge_distances.append(d)
                    else:  # case 3) line is diagonal, opposite reciprocal is perpendicular to that line

                        # help understanding whats going on here:
                        # https://www.youtube.com/watch?v=vwFoPJjxGF0

                        # find slope m = (y2-y1)/(x2-x1)
                        slope = top_of_fraction / bottom_of_fraction
                        # get y-axis intercept
                        y_axis_intercept = (-1 * start_point['x'] * slope) + start_point['y']

                        # get opposite reciprocal
                        opp_rec = -1 / slope
                        # get point and opposite reciprocal's y-axis intercept
                        y_axis_intercept_opp = (-1 * line_data['x'] * opp_rec) + line_data['y']

                        # find x,y intercept of both lines

                        # get combined slope and intercepts
                        combined_slope = slope - opp_rec
                        combined_intercepts = y_axis_intercept_opp - y_axis_intercept

                        # get point where the two lines intercept
                        x_intercept = combined_intercepts / combined_slope
                        y_intercept = slope * x_intercept + y_axis_intercept  # y = mx + b

                        # use distance formula to find distance between x,y intercepts
                        # and the point found from the touch controller
                        # DISTANCE FORMULA:
                        # distance = sqrt{ (x2 -x1)^2 + (y2 - y1)^2 }
                        d = math.sqrt((x_intercept - line_data['x']) ** 2 + (y_intercept - line_data['y']) ** 2)

                        if d < max_distance:
                            if is_core:
                                core_distances.append(d)
                            else:
                                edge_distances.append(d)

        is_core = False  # this is called after all core data has been plotted

    # save the figure and name it
    plt.savefig(fname="lin_image.png", format='png')
    plt.close()  # close the figure when finished
    img = Image.open("lin_image.png")
    r, g, b, a = img.split()
    img = Image.merge("RGB", (r, g, b))
    img_name = 'lin_graph_for_excel_part_' + part_name + str(test_num) + '.bmp'
    img.save(img_name)

    # save all data and return it with the linearity
    all_data = list()
    all_data.extend(core_lines_and_points)
    all_data.extend(edge_lines_and_points)

    return core_distances, edge_distances, all_data


class TestManager:

    def __init__(self, robot_controller: RobotController):
        """
        constructor for the test manager
        :param robot_controller: robot controller being used to run tests
        """
        self.robot_controller = robot_controller
        self.touch_controller = TouchController()
        self._x_range, self._y_range = self.touch_controller.get_range()
        self._dxf_reader = None

        self._xy_switched = self._x_flip = self._y_flip = None
        self._num_x_nodes = self._num_y_nodes = None
        self._is_move_reading = False
        self._z_start = None

        self._test_parameters = []
        # FIXME self._tests_to_run = ["Accuracy", "Signal-to-Noise (SNR)", "Jitter", "Linearity"]
        self._tests_to_run = None
        # accuracy parameters
        self._acc_num_touches = 0
        self._acc_touch_duration = 0
        self._acc_sec_between_touch = 0
        self._acc_probe_size = 0
        self._acc_iterations = 0
        self._acc_edge_pass_fail = 0
        self._acc_core_pass_fail = 0
        # SNR parameters
        self._snr_num_noise_samples = 0
        self._snr_num_signal_samples = 0
        self._snr_sec_between_touch = 0
        self._snr_probe_size = 0
        self._snr_iterations = 0
        self._snr_edge_pass_fail = 0
        self._snr_core_pass_fail = 0
        # Jitter parameters
        self._jit_num_touches = 0
        self._jit_touch_duration = 0
        self._jit_sec_between_touch = 0
        self._jit_probe_size = 0
        self._jit_iterations = 0
        self._jit_edge_pass_fail = 0
        self._jit_core_pass_fail = 0
        # Linearity parameters
        self._lin_path_velocity = 0
        self._lin_sec_between_touch = 0
        self._lin_probe_size = 0
        self._lin_iterations = 0
        self._lin_edge_pass_fail = 0
        self._lin_core_pass_fail = 0

        # initialize results to be empty lists
        self._acc_results = []
        self._jit_results = []
        self._lin_results = []
        self._snr_results = []

    ####
    # setter/getter/upload methods

    def get_touch_controller_type(self):
        """
        :return: touch controller being used
        """
        return self.touch_controller.get_touch_controller_type()

    def set_z_start(self, z: float):
        """
        sets the Z axis for the robot to move to
        :param z: float representing where to move the finger
        :return: None
        """
        self._z_start = z

    def set_dxf_reader(self, reader: DXFReader):
        """
        sets the robot's DXF reader
        :param reader: DXF reader object to set
        :return: N/A
        """
        self._dxf_reader = reader

    def set_touch_controller(self, controller_name: str) -> None:
        """
        sets the TouchController's hardware based on the input string
        :param controller_name: Hardware name associated with the controller
        :return: None
        """
        self.touch_controller.set_touch_controller(controller_name)

    def upload_tests_to_run(self, tests: list):
        """
        upload a list of tests to run
        :param tests: list containing which tests to run in a specified order
                      *** tests should be strings ***
        :return: N/A
        """
        self._tests_to_run = tests

    def upload_configuration_data(self, params: list, debug=False):
        """
        Uploads the testing parameters
        The list is comprised of multiple lists, each holding the parameters for
        the associated tests in these indexes with their associated parameter indexes:
        0:ACC::
            0: number of touches for each point
            1: touch duration
            2: Sec between touches
            3: Probe Size(mm)
            4: Test iterations
        1:SNR::
            0: number of noise samples
            1: number of signal samples
            2: Sec between touches
            3: Probe Size(mm)
            4: Test iterations
        2:JIT::
            0: Touch duration
            1: Sec between touches
            2: Probe Size(mm)
            3: Test iterations
        3:LIN::
            0: Path Velocity
            1: Sec between touches
            2: Probe Size(mm)
            3: Test iterations
        4:PASS/FAIL CRITERIA::
            0: Accuracy PF conditions
                0: edge PF condition
                1: core PF condition
            1: Signal-to-Noise PF conditions
                0: edge PF condition
                1: core PF condition
            2: jitter PF conditions
                0: edge PF condition
                1: core PF condition
            3: Linearity PF conditions
                0: edge PF condition
                1: core PF condition
        :param debug: boolean that determines if the data is printed when it is uploaded
        :param params: test parameters following the above format
        :return: N/A
        """

        # update the size of the nodes
        node_length = params.pop(-1)
        self._num_x_nodes = node_length[0]
        self._num_y_nodes = node_length[1]
        self.touch_controller.update_number_of_nodes(self._num_x_nodes, self._num_y_nodes)

        pf_criteria = params.pop(-1)

        # get pass/fail criteria from pf_criteria's tuples
        acc_criteria = pf_criteria[0]
        self._acc_edge_pass_fail = acc_criteria[0]
        self._acc_core_pass_fail = acc_criteria[1]
        snr_criteria = pf_criteria[1]
        self._snr_edge_pass_fail = snr_criteria[0]
        self._snr_core_pass_fail = snr_criteria[1]
        jit_criteria = pf_criteria[2]
        self._jit_edge_pass_fail = jit_criteria[0]
        self._jit_core_pass_fail = jit_criteria[1]
        lin_criteria = pf_criteria[3]
        self._lin_edge_pass_fail = lin_criteria[0]
        self._lin_core_pass_fail = lin_criteria[1]

        self._test_parameters = params

        # get lists of parameters from input
        acc_params = self._test_parameters[0]
        snr_params = self._test_parameters[1]
        jit_params = self._test_parameters[2]
        lin_params = self._test_parameters[3]
        # acc param setting:
        self._acc_num_touches = acc_params[0]
        self._acc_touch_duration = acc_params[1]
        self._acc_sec_between_touch = acc_params[2]
        self._acc_probe_size = acc_params[3]
        self._acc_iterations = int(acc_params[4])
        # snr param setting:
        self._snr_num_noise_samples = int(snr_params[0])
        self._snr_num_signal_samples = int(snr_params[1])
        self._snr_sec_between_touch = snr_params[2]
        self._snr_probe_size = snr_params[3]
        self._snr_iterations = int(snr_params[4])
        # jit param setting:
        self._jit_num_touches = jit_params[0]
        self._jit_touch_duration = jit_params[1]
        self._jit_sec_between_touch = jit_params[2]
        self._jit_probe_size = jit_params[3]
        self._jit_iterations = int(jit_params[4])
        # lin param setting:
        self._lin_path_velocity = lin_params[0]
        self._lin_sec_between_touch = lin_params[1]
        self._lin_probe_size = lin_params[2]
        self._lin_iterations = int(lin_params[3])

        if debug:
            print("Printing Test Parameters that were uploaded from MainFrame:\n")
            print("Accuracy:")
            print(self._test_parameters[0])
            print("Signal-to-Noise (SNR):")
            print(self._test_parameters[1])
            print("Jitter:")
            print(self._test_parameters[2])
            print("Linearity:")
            print(self._test_parameters[3])

    def set_finger_offset(self, offset: tuple):
        """
        Sets the offset from the center of the robot's arm
        :param offset: finger offset from the 0, 0 point of the robot as a tuple
                       offset[0] = x
                       offset[1] = y
        :return: N/A
        """

        # reset offsets for new offset when uploading configuration multiple times in a row
        if self._dxf_reader:
            self._dxf_reader.reset_offsets()

        x_offset = offset[0]
        y_offset = offset[1]
        if self._dxf_reader:
            self._dxf_reader.update_offset(x_offset, y_offset)

    def save_results(self, filepath: str, sensor_type: str, sensor_config: str):
        """
        saves the results to an Excel file using the ExcelSaver class
        :param filepath: filepath to save to
        :param sensor_type: type of sensor used
        :param sensor_config: configuration of sensor used
        :return: N/A
        """
        # create lists for passing into ExcelSaver
        # this is a little convoluted, but it works to make the number of parameters passed in small
        # so its either this or have 25+ parameters to pass into ExcelSaver
        # if you are a developer and ever want to improve this, I would recommend adding more methods to the
        # ExcelSaver class and just have all the self._acc_results, self._jit_results, etc. in the saver class
        acc_params = [self._acc_num_touches, self._acc_touch_duration, self._acc_sec_between_touch,
                      self._acc_probe_size, self._acc_iterations, self._acc_core_pass_fail, self._acc_edge_pass_fail]
        snr_params = [self._snr_num_noise_samples, self._snr_num_signal_samples, self._snr_sec_between_touch,
                      self._snr_probe_size, self._snr_iterations, self._snr_core_pass_fail, self._snr_edge_pass_fail]
        jit_params = [self._jit_num_touches, self._jit_touch_duration, self._jit_sec_between_touch,
                      self._jit_probe_size, self._jit_iterations, self._jit_core_pass_fail, self._jit_edge_pass_fail]
        lin_params = [self._lin_path_velocity, self._lin_sec_between_touch, self._lin_probe_size, self._lin_iterations,
                      self._lin_core_pass_fail, self._lin_edge_pass_fail]
        sensor_data = [sensor_type, sensor_config, self.touch_controller.get_touch_controller_type()]

        ExcelSaver(filepath, acc_params, snr_params, jit_params, lin_params, self._num_x_nodes, self._num_y_nodes,
                   acc_results=self._acc_results, snr_results=self._snr_results, jit_results=self._jit_results,
                   lin_results=self._lin_results, conversion_function=self.convert_robot_to_screen_coordinates,
                   sensor_data=sensor_data)
        self._snr_results.clear()
        self._acc_results.clear()
        self._jit_results.clear()
        self._lin_results.clear()
    ####
    # orientation methods

    def orient(self):
        """
        Orients the axes of the screen, required to call this at least once prior to running test.
        :return: None
        """
        self.robot_controller.set_speed_point_to_point(250)  # set speed to be fast
        self._x_range, self._y_range = self.touch_controller.get_range()  # set the x and y ranges

        corners = list()  # initialize corners
        origin_corner = None  # initialize origin corner
        origin_point = [9999, 9999]  # initialize origin point to be stupid big so it will be overwritten
        x_max = y_max = 0  # initialize the maxes to be tiny lads so it will be overwritten
        x_min = y_min = 9999 # initialize mins to be large so they will be overwritten
        offset_ratio = .25  # offset ratio is how much off the edges the finger will poke that board

        # iterate through and get x and y maximums and minimums
        for corner in self._dxf_reader.get_active_area().get_points():
            if corner[0] > x_max:
                x_max = corner[0]  # set new max
            if corner[1] > y_max:
                y_max = corner[1]  # set new max
        
        for corner in self._dxf_reader.get_active_area().get_points():
            if corner[0] < x_min:
                x_min = corner[0]
            if corner[1] < y_min:
                y_min = corner[1]
        
        print(x_max)
        print(y_max)
        print(x_min)
        print(y_min)
        
        # iterate over every corner and test to see the screen coordinates
        for corner in self._dxf_reader.get_active_area().get_points():
            # get the offsets so the finger touches on the board, and not on the corners (can cause errors if
            # offsets are not applied to the move)
            x_offset = -1 * offset_ratio if are_nums_close(corner['x'], x_max, closeness=1) else offset_ratio
            y_offset = -1 * offset_ratio if are_nums_close(corner['y'], y_max, closeness=1) else offset_ratio

            # move finger onto board, then off
            self.robot_controller.move(corner['x'] + x_offset * (x_max - x_min), corner['y'] + y_offset * (y_max - y_min), self._z_start - Z_OFFSET,
                                       is_continuous=False)
            self.robot_controller.move(corner['x'] + x_offset * (x_max - x_min), corner['y'] + y_offset * (y_max - y_min), self._z_start,
                                       is_continuous=False)
            self.robot_controller.move(corner['x'] + x_offset * (x_max - x_min), corner['y'] + y_offset * (y_max - y_min), self._z_start - Z_OFFSET,
                                       is_continuous=False)
            pt = self.touch_controller.get_orientation_coordinates()  # get the *SCREEN COORDINATES* (not mm)
            corners.append((corner, pt))  # append a tuple to keep the data together
            # see if point is the origin (subtracting 50 in case of slight changes in reading)
            # pdb.set_trace()
            if pt[0] - 50 < origin_point[0] and pt[1] - 50 < origin_point[1]:
                origin_corner = corner  # set origin_corner *CORNER* to be the point
                origin_point = pt  # set origin_point *NOT POINT OBJECT* to be list of screen coordinates


        self.robot_controller.move_home()  # go back home (like my father never did)                         <--- joking
        # initialize points
        pos_x_pt = None
        pos_y_pt = None

        # iterate over all corners to find the positive X and Y axis
        for tup in corners:
            pt = tup[1]  # get the screen point *NOT POINT OBJECT*
            if pt != origin_point:
                if are_nums_close(pt[0], origin_point[0]) and not are_nums_close(pt[1], origin_point[1]):
                    pos_y_pt = tup[0]  # set positive Y axis *POINT OBJECT*
                if are_nums_close(pt[1], origin_point[1]) and not are_nums_close(pt[0], origin_point[0]):
                    pos_x_pt = tup[0]  # set positive X axis *POINT OBJECT*

        if pos_x_pt is not None and pos_y_pt is not None:  # only do this if the positive axes were set
            self.orientation_figure_axes(origin_corner, pos_x_pt, pos_y_pt)  # figure those axes
        else:
            raise errors.InvalidAxes("Could not determine the positive axes.")

        self._dxf_reader.get_active_area().set_origin(origin_corner)  # set the origin got from the Orientation
        self.robot_controller.set_orientation_status(True)  # remember that this lad was Oriented
        return self._xy_switched, self._x_flip, self._y_flip

    def orientation_probe(self, point: Point, x_max: float, y_max: float, debug=False):
        """
        probes a point to get its screen data

        :param point: point being used
        :param x_max: maximum X value
        :param y_max: maximum Y value
        :param debug: bool determining if debug data is output to the console
        :return: orientation coordinates
        """
        offset_ratio = 12
        return_value = (1e9, 1e9)

        while return_value[0] > self._x_range or return_value[1] > self._y_range:
            # get directions to test
            x_offset = -1 * offset_ratio if point['x'] == x_max else offset_ratio
            y_offset = -1 * offset_ratio if point['y'] == y_max else offset_ratio

            self.robot_controller.move(point['x'] + x_offset, point['y'] + y_offset, self._z_start - Z_OFFSET,
                                       is_continuous=False)
            self.robot_controller.move(point['x'] + x_offset, point['y'] + y_offset, self._z_start, is_continuous=False)
            if debug:
                print("#####################################################\nNEW MOVE AT (" + str(point[0] + x_offset))
            time.sleep(1)
            self.robot_controller.move(point['x'] + x_offset, point['y'] + y_offset, self._z_start - Z_OFFSET,
                                       is_continuous=False)
            return_value = self.touch_controller.get_orientation_coordinates(max_iterations=100)
        return return_value

    def orientation_figure_axes(self, origin: Point, positive_x: Point, positive_y: Point) -> None:
        """
        figures the direction of the screen's axes
        :param origin: origin point of the screen
        :param positive_x: positive X direction of screen
        :param positive_y: positive Y direction of screen
        :return: N/A
        """
        if positive_x == positive_y:
            raise errors.InvalidAxes("Positive X and positive Y axis match, error probably occurred with getting"
                              " data from the touch controller.")

        # print("SCREEN WIDTH: " + str(self._screen_width))
        # print("SCREEN HEIGHT: " + str(self._screen_height))

        # case where X and Y axis are on the same line
        # Ex:
        # +------------------>       <-------------------+
        # |                  X       X                   |
        # |     Robot X,Y                 Screen X,Y     |
        # |                                              |
        # |                                              |
        # V  Y                                        Y  V
        #
        # Note how the X and Y axis arent the same, however they are in the same directions
        # (as in, x axis is still left-right, Y axis is still up-down)
        if are_nums_close(positive_x['y'], origin['y'], closeness=5) and\
                are_nums_close(positive_y['x'], origin['x'], closeness=5):
            self._xy_switched = False
            self._x_flip = positive_x['x'] < origin['x']  # determine if robot's x axis is flipped or not
            self._y_flip = positive_y['y'] < origin['y']  # determine if robot's y axis is flipped or not

        else:
            # case where X and Y axis are not on the same line
            # Ex:
            # +------------------>       <-------------------+
            # |                  X       Y                   |
            # |     Robot X,Y                 Screen X,Y     |
            # |                                              |
            # |                                              |
            # V  Y                                        X  V
            # Note how the X and Y axis arent the same *AND* the directions have changed
            # (x-axis on robot is left-right, X axis on screen is up-down, vice versa for the Y axis)
            self._xy_switched = True
            self._x_flip = positive_y['x'] < origin['x']  # determine if robot's x axis is flipped or not
            self._y_flip = positive_x['y'] < origin['y']  # determine if robot's y axis is flipped or not

    ####
    # end getter/setter

    def reset_touch_controller(self) -> bool:
        """
        Resets the touch controller (crazy!)
        :return: bool indicating if the reset was successful
        """
        return self.touch_controller.reset()

    def get_progress_dialog_size(self):
        """
        gets the size of the progress dialog
        :return: integer of the dialog range
        """
        dialog_range = 0

        for test in self._tests_to_run:
            if test == "Linearity":
                dialog_range += self._lin_iterations
            elif test == "Accuracy":
                dialog_range += self._acc_iterations
            elif test == "Signal-to-Noise (SNR)":
                dialog_range += self._snr_iterations
            elif test == "Jitter":
                dialog_range += self._jit_iterations
        return int(dialog_range)

    ####
    # conversion methods

    def convert_robot_to_screen_coordinates(self, x_robot: float, y_robot: float):
        """
        converts robots XY coordinates to units that are in line with the screen's coordinates
        :param x_robot: x coordinate of the robot
        :param y_robot: y coordinate of the robot
        :return: point representing a point on the screen
        """

        if self._xy_switched:  # case 1: the X and Y axes of the screen are flip in comparison to the robot
            if self._x_flip:
                centered_x = self._dxf_reader.get_origin()['y'] - y_robot
            else:
                centered_x = y_robot - self._dxf_reader.get_origin()['x']

            if self._y_flip:
                centered_y = self._dxf_reader.get_origin()['x'] - x_robot
            else:
                centered_y = x_robot - self._dxf_reader.get_origin()['y']
        else:  # case 2: the X and Y axes of the screen match the robot
            if self._x_flip:
                centered_x = self._dxf_reader.get_origin()['x'] - x_robot
            else:
                centered_x = x_robot - self._dxf_reader.get_origin()['x']

            if self._y_flip:
                centered_y = self._dxf_reader.get_origin()['y'] - y_robot
            else:
                centered_y = y_robot - self._dxf_reader.get_origin()['y']

        return Point(centered_x, centered_y)

    def screen_units_to_mm(self, x_screen: int, y_screen: int, debug=False):
        """
        converts screen units into usable mm units
        screen units are the x and y ranges of the screen
        :param x_screen: screen X point
        :param y_screen: screen Y point
        :param debug: bool indicating if debug data is output
        :return: Point representing the screen units in mm
        """
        # convert screen units to mm units
        if self._xy_switched:
            x_mm = round(x_screen / self._x_range * self._dxf_reader.get_active_area().get_height(), 2)
            y_mm = round(y_screen / self._y_range * self._dxf_reader.get_active_area().get_width(), 2)
        else:
            x_mm = round(x_screen / self._x_range * self._dxf_reader.get_active_area().get_width(), 2)
            y_mm = round(y_screen / self._y_range * self._dxf_reader.get_active_area().get_height(), 2)
        if debug:
            if y_mm < 0 or x_mm < 0:
                print("BAD POINT GENERATED: (" + str(x_mm) + ", " + str(y_mm) + ")")
            elif y_mm > 200 or x_mm > 200:
                print("BAD POINT GENERATED: (" + str(x_mm) + ", " + str(y_mm) + ")")
        return Point(x_mm, y_mm)

    ####
    # end conversion methods

    ####
    # robot controller methods

    def run_tests(self, tests: list, dlg, part_name: str, is_large_read=False):
        """
        runs the tests
        :param tests: list of tests to be ran
        :param dlg: progressdialog to let user know state of tests
        :param part_name: name of the part being tested
        :param is_large_read: bool determining if the SNR test is a large read (5x5) or a small read (3x3).
        :return: bool determining if the tests were ran successfully
        """
        if not self.robot_controller.is_oriented():  # you need to orient the screen before using it, silly
            raise errors.NotOriented("Screen must be oriented before running tests.")

        is_connected = True  # initialize is_connected variable
        # run basic move home command to see if robot is connected
        try:
            self.robot_controller.move_home(timeout=12)
        except TimeoutError:
            is_connected = False

        # clear previous runs of the tests

        # only run tests if robot is connected
        if is_connected:
            dlg.SetRange(self.get_progress_dialog_size())
            test_num = dlg.GetValue()
            # iterate over all tests to run and run them
            for test in tests:
                if test == "Accuracy":
                    self.robot_controller.set_speed_point_to_point(200)
                    all_acc_core_values = list()
                    all_acc_edge_values = list()
                    all_acc_full_values = list()
                    for i in range(self._acc_iterations):  # run test num_iterations number timer
                        self.touch_controller.clear_buffer()
                        core_values, edge_values, full_values = self.run_acc_test()
                        all_acc_core_values.append(core_values)
                        all_acc_edge_values.append(edge_values)
                        all_acc_full_values.append(full_values)
                        test_num += 1
                        dlg.Update(test_num, "Accuracy test " + str(i + 1) + " completed.")
                    self._acc_results.append([all_acc_core_values, all_acc_edge_values, all_acc_full_values, part_name])
                elif test == "Jitter":
                    self.robot_controller.set_speed_point_to_point(200)
                    all_jit_core_values = list()
                    all_jit_edge_values = list()
                    for i in range(self._jit_iterations):  # run test num_iterations number timer
                        self.touch_controller.clear_buffer()
                        jit_core, jit_edge = self.run_jit_test(i + 1, self._jit_num_touches, part_name=part_name)
                        test_num += 1
                        dlg.Update(test_num, "Jitter test " + str(i + 1) + " completed.")
                        all_jit_core_values.append(jit_core)
                        all_jit_edge_values.append(jit_edge)
                    self._jit_results.append([all_jit_core_values, all_jit_edge_values, part_name])
                elif test == "Linearity":
                    self.robot_controller.set_speed_point_to_point(50)

                    all_lin_core_values = list()
                    all_lin_full_values = list()
                    all_lines_and_points = list()

                    for i in range(1, self._lin_iterations + 1):  # run test num_iterations number timer
                        self.touch_controller.clear_buffer()
                        core, edge, lines_and_points = self.run_lin_test(i, part_name)                        
                        all_lin_full_values.append(edge)                        
                        all_lin_core_values.append(core)
                        all_lines_and_points.append(lines_and_points)
                        test_num += 1
                        dlg.Update(test_num, "Linearity test " + str(i) + " completed.")
                    self._lin_results.append([all_lin_core_values, all_lin_full_values, all_lines_and_points, part_name])
                elif test == "Signal-to-Noise (SNR)":
                    self.robot_controller.set_speed_point_to_point(200)
                    all_snr_core_values = list()
                    all_snr_full_values = list()
                    for i in range(self._snr_iterations):  # run test num_iterations number timer
                        self.touch_controller.clear_buffer()
                        snr_core_vals, snr_full_vals = self.run_snr_test(is_large_read=is_large_read)
                        all_snr_core_values.append(snr_core_vals)
                        all_snr_full_values.append(snr_full_vals)
                        test_num += 1
                        dlg.Update(test_num, "SNR test " + str(i + 1) + " completed.")
                    self._snr_results.append([all_snr_core_values, all_snr_full_values, part_name])
                else:
                    raise ValueError("Not a valid test: " + test)
                dlg.Update(test_num, test + " test completed successfully.")
                self.robot_controller.move_home()
            self.robot_controller.set_speed_point_to_point(50)
            dlg.Update(dlg.GetRange(), "Tests complete.")
        else:
            return False  # robot not connected, end run tests
        return True  # tests ran, return True

    ####
    # Accuracy Methods

    def run_acc_test(self):
        """
        runs the accuracy test
        :return: the calculated accuracy of the core and edge, respectively
        """
        # this one does touches, do each touch point on screen
        # get reported x and y (Xr & Yr) from the touch controller,
        # then the physical coordinate (Xp & Yp) of the touch.
        # calculate accuracy of that spot with:
        # Xerr = Xr - Xp
        # Yerr = Yr - Yp
        # acc = sqrt(Xerr^2 + Yerr^2)
        core_values = []
        full_values = []
        edge_values = []
        # iterate over each edge accuracy point and perform a test
        for touch_point in self._dxf_reader.get_accuracy_edge():
            # touch point format: [x pt, y pt]
            touched_points = self.accuracy_touch_test(touch_point)
            edge_values.append(touched_points)
            full_values.append(touched_points)
            self.touch_controller.clear_buffer()
        # iterate over each core accuracy point and perform a test
        for touch_point in self._dxf_reader.get_accuracy_core():
            # touch point format: [x pt, y pt]
            touched_points = self.accuracy_touch_test(touch_point)
            core_values.append(touched_points)
            full_values.append(touched_points)
            self.touch_controller.clear_buffer()
        return calc_accuracy(core_values),\
               calc_accuracy(edge_values),\
               calc_accuracy(full_values)

    def accuracy_touch_test(self, point: Point, debug=False):
        """
        performs a touch test at the point passed in as a parameter
        :param point: point to test
        :param debug: bool showing debug data if true
        :return: list of the point that was touched (index 0) and registered screen units
        """
        # create list with index 0 being the actual point evaluated
        ret_list = [self.convert_robot_to_screen_coordinates(point['x'], point['y'])]
        self.robot_controller.move(point['x'], point['y'], self._z_start - Z_OFFSET, is_continuous=False)  # move to start position
        for i in range(int(self._acc_num_touches)):
            if i != 0:
                time.sleep(self._acc_sec_between_touch)  # wait time_between_touches before proceeding
            self.robot_controller.move(point['x'], point['y'], self._z_start, is_continuous=False)  # move finger onto the board
            time.sleep(self._acc_touch_duration)  # wait hold_duration
            self.robot_controller.move(point['x'], point['y'], self._z_start - Z_OFFSET)  # move finger off of board
            registered_touch = self.touch_controller.get_touch_coordinate()  # get a Point touched

            if debug:
                print("##############################################")
                print("point before manipulation: " + str(point))
                print("TRYING TO TOUCH POINT:          " + str(ret_list[0]))
                print("CONTROLLER REGISTERED TOUCH AT: " +
                      str(self.screen_units_to_mm(registered_touch[0], registered_touch[1])))

            ret_list.append(self.screen_units_to_mm(registered_touch[0], registered_touch[1]))
        return ret_list

    ####
    # Linearity Methods

    def run_lin_test(self, test_iteration: int, part_name: str):
        """
        performs a linearity test on all lines read in from the linearity layer of the .dxf file
        :param part_name:
        :param test_iteration: iteration of the test
        :return: calculated linearity
        """
        # get core and edge requirements
        # save min, deviation, max deviation, and average of the few
        # if the max exceeds the expected, then the test fails (page 53 in thesis)

        core_lines_and_points = list()
        edge_lines_and_points = list()


        for line in self._dxf_reader.get_linearity_core():
            start_pt = self.convert_robot_to_screen_coordinates(line.get_start_x(), line.get_start_y())
            end_pt = self.convert_robot_to_screen_coordinates(line.get_end_x(), line.get_end_y())
            lines_and_points = [Line(start_pt, end_pt)]
            point_from_touchscreen = self.line_test(line)
            for point in point_from_touchscreen:
                lines_and_points.append(point)
            time.sleep(self._lin_sec_between_touch)
            core_lines_and_points.append(lines_and_points)

        for line in self._dxf_reader.get_linearity_edge():
            start_pt = self.convert_robot_to_screen_coordinates(line.get_start_x(), line.get_start_y())
            end_pt = self.convert_robot_to_screen_coordinates(line.get_end_x(), line.get_end_y())
            lines_and_points = [Line(start_pt, end_pt)]
            point_from_touchscreen = self.line_test(line)
            for point in point_from_touchscreen:
                lines_and_points.append(point)
            time.sleep(self._lin_sec_between_touch)
            edge_lines_and_points.append(lines_and_points)
        return calc_linearity(core_lines_and_points, edge_lines_and_points, part_name, test_iteration)

    def line_test(self, line: Line):
        """
        performs a line test (moving from start of line to end of line)
        :param line: line to perform line test on
        :return: bool indicating the move was successful
        """
        # set speed to be fast to get to starting point of line
        self.robot_controller.set_speed_point_to_point(200)
        # move to start point
        self.robot_controller.move(line.get_start_x(), line.get_start_y(), self._z_start - Z_OFFSET, is_continuous=False)
        # clear old messages
        self.touch_controller.clear_buffer()
        # put finger on screen
        self.robot_controller.move(line.get_start_x(), line.get_start_y(), self._z_start, is_continuous=False)
        # set speed to 40 mm/sec to get a good amount of data points
        self.robot_controller.set_speed_point_to_point(self._lin_path_velocity)
        # move to end of line and return results
        # this move method goes to the wait_and_read method which utilizes multithreading
        # FIXME find new way of doing this
        return self.wait_and_read(line.get_end_x(), line.get_end_y(), self._z_start)

    def lin_read_wrapper(self, rfc, q: queue.Queue, lock: threading.Lock):
        """
        Wrapper method for use in multithreading the read method
        this method will only ever have read_from_controller and a queue passed in from the
        wait_and_read method
        (if its not broken, don't fix it!!)

        :param rfc: will ONLY be the read_from_controller method.
        :param q: Queue to put method into for retrieval in main thread
        :return: Nothing
        """
        #q.put(rfc())
        mm_coordinates = list()
        # iterate while the machine is "move reading"
        
        lock.acquire()
        is_move_reading = self._is_move_reading
        lock.release()
        
        while is_move_reading:
            screen_coordinates = self.touch_controller.read_all_points()
            for point in screen_coordinates:
                coordinates_mm = self.screen_units_to_mm(point[0], point[1])
                mm_coordinates.append(coordinates_mm)
            lock.acquire()
            is_move_reading = self._is_move_reading
            lock.release()
            # time.sleep(.5)                  
        q.put(mm_coordinates)
        
        

    def lin_move_wrapper(self, mv, goal_x: float, goal_y: float, goal_z: float, q: queue.Queue, lock: threading.Lock):
        """
        wrapper method for multithreading the move method
        (if its not broken, don't fix it!!)
        :param mv: the move method { self.move() }
        :param goal_x: x param for move method
        :param goal_y: y param for move method
        :param goal_z: z param for move method
        :param q: Queue to put method into for retrieval in main thread
        :return: Nothing
        """
        
        lock.acquire()
        self._is_move_reading = True
        lock.release()
        q.put(mv(goal_x, goal_y, goal_z))      
        lock.acquire()
        self._is_move_reading = False
        lock.release()

    def read_from_controller(self) -> list:
        """
        reads from the controller while the machine is "move reading"
        :return: list of coordinates, wherein the coordinates are in a list form:
                 EX:
                    [ [x1, y1], [x2, y2], [x3, y3], ....., [xN, yN] ]
        """
        mm_coordinates = list()
        # iterate while the machine is "move reading"
        
        self._is_move_reading = self._is_move_reading
        
        while self._is_move_reading:
            screen_coordinates = self.touch_controller.read_all_points()
            for point in screen_coordinates:
                coordinates_mm = self.screen_units_to_mm(point[0], point[1])
                mm_coordinates.append(coordinates_mm)
            _is_move_reading = self._is_move_reading
            # time.sleep(.5)
        self.touch_controller.clear_buffer()
        return mm_coordinates

    def wait_and_read(self, goal_x: float, goal_y: float, goal_z: float):
        """
        special method which utilized multithreading to both move the machine and
        read input from the touch controller.
        :param goal_x: x param for move method
        :param goal_y: y param for move method
        :param goal_z: z param for move method
        :return: data gathered from the touch controller
        """

        retry = 10

        while retry:
            print(retry)
            q = queue.Queue()  # initialize Queue for multithreading
            lock = threading.Lock()
            # initialize two threads  by passing in the wrapper function
            t1 = threading.Thread(target=self.lin_move_wrapper, args=(self.robot_controller.get_move_function(),
                                                                      goal_x, goal_y, goal_z, q, lock))
            t2 = threading.Thread(target=self.lin_read_wrapper, args=(self.read_from_controller, q, lock))
            # start threads and join them so this main thread waits for them to finish
            t1.start()
            t2.start()
            t1.join()
            print("1 finished")
            t2.join()
            # return Queue[1], which is the touch controller's data
            print("1")
            ans1 = q.get_nowait()
            ans2 = q.get_nowait()         
            print("2")
            if type(ans1) is bool and type(ans2) is list:
                return ans2
            else:
                retry -= 1
        raise IOError

    ####
    # Jitter Methods

    def run_jit_test(self, test_num: int, num_touches: int, part_name: str):
        """
        runs the jitter test
        :return: calculated jitter for the core and edge
        """

        jitter_edge = list()
        jitter_core = list()

        # Initialize graph
        fig, ax = plt.subplots()
        img_title = "Jitter Test " + part_name + ", Iteration " + str(test_num)
        ax.set(xlabel="X - Axis (mm)", ylabel="Y - Axis (mm)", title=img_title)

        for touch_point in self._dxf_reader.get_jitter_edge():
            point_data = self.jitter_touch_test(touch_point, touches=num_touches,
                                                hold_duration=self._jit_touch_duration)
            jitter_edge.append(point_data)
            screen_pt = self.convert_robot_to_screen_coordinates(touch_point['x'], touch_point['y'])
            plt.plot(screen_pt['x'], screen_pt['y'], marker='x', color='red', markersize=4)
            time.sleep(self._jit_sec_between_touch)

        for touch_point in self._dxf_reader.get_jitter_core():
            point_data = self.jitter_touch_test(touch_point, touches=num_touches,
                                                hold_duration=self._jit_touch_duration)
            jitter_core.append(point_data)
            screen_pt = self.convert_robot_to_screen_coordinates(touch_point['x'], touch_point['y'])
            plt.plot(screen_pt['x'], screen_pt['y'], marker='x', color='blue', markersize=4)
            time.sleep(self._jit_sec_between_touch)

        # add jitter-ed points to the graph
        for group in [jitter_core, jitter_edge]:
            for jittered_point_data in group:
                is_first_point = True
                for point in jittered_point_data:
                    if not is_first_point:
                        plt.plot(point['x'], point['y'], marker='o', color='black', markersize=2)
                    else:
                        is_first_point = False

        # save the figure and name it
        plt.savefig(fname="jit_image.png", format='png')
        plt.close()  # close the figure when finished
        img = Image.open("jit_image.png")
        r, g, b, a = img.split()
        img = Image.merge("RGB", (r, g, b))
        img_name = 'jit_graph_for_excel_' + part_name + str(test_num) + '.bmp'
        img.save(img_name)

        return calc_jitter(jitter_core), calc_jitter(jitter_edge)

    def jitter_touch_test(self, point: Point, touches=2, hold_duration=.5) -> list:
        """
        runs a jitter test on a (x,y) point given that the Z axis was set prior
        :param point:
        :param hold_duration:
        :param touches:
        :return:
        """
        # PRESS AND HOLD
        x = point['x']
        y = point['y']

        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)  # move above touch point
        # create list of points where the 0th index is the point its at and the following points are
        # the jitter calculations
        jitter_points = [self.convert_robot_to_screen_coordinates(x, y)]
        # run touches times
        for i in range(int(touches)):
            points = self.jitter_touch_non_mt(point, hold_duration)
            jitter_points.extend(points)
        return jitter_points

    def jitter_touch(self, point: Point, hold_duration=.5):
        """
        method used with multithreading.
        touches the screen

        :param point: point being touched
        :param hold_duration: how long to hold
        :return: N/A
        """
        x = point['x']
        y = point['y']
        self._is_move_reading = True
        self.robot_controller.move(x, y, self._z_start)
        time.sleep(hold_duration)  # wait hold_duration seconds before moving again
        # move back off of the screen
        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)
        self._is_move_reading = False

    def jitter_touch_non_mt(self, point: Point, hold_duration):
        """
        non-multithreaded touch test for jitter
        :param point: point being evaluated
        :param hold_duration: how long to hold on the board
        :return: list of points evaluated
        """
        x = point['x']
        y = point['y']

        self.touch_controller.clear_buffer()

        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)
        self.robot_controller.move(x, y, self._z_start)

        mm_coordinates = list()

        time_ns = time.time_ns()
        print(time_ns)

        while time.time_ns() - time_ns < hold_duration * 1E9:
            screen_coordinates = self.touch_controller.read_all_points()
            for point in screen_coordinates:
                coordinates_mm = self.screen_units_to_mm(point[0], point[1])
                mm_coordinates.append(coordinates_mm)

        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)
        return mm_coordinates

    """
    def jitter_touch_move_then_read(self, point: Point, hold_duration):
        
        non-multithreaded touch test for jitter
        :param point: point being evaluated
        :param hold_duration: how long to hold on the board
        :return: list of points evaluated
        
        x = point['x']
        y = point['y']

        self.touch_controller.clear_buffer()

        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)
        self.robot_controller.move(x, y, self._z_start)
        time.sleep(hold_duration)
        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)

        pdb.set_trace()
        msgs = self.touch_controller.num_messages_to_read()
        points = self.touch_controller.read_touch_point(msgs)
        return points
    """

    def jitter_touch_mt(self, point: Point, hold_duration=.5):
        """
        multithreading touch test for jitter
        :param point: point being evaluated
        :param hold_duration: how long to hold on the board
        :return: list of points evaluated
        """
        q = queue.Queue()  # initialize Queue for multithreading
        # initialize two threads  by passing in the wrapper function
        t1 = threading.Thread(target=self.jit_move_wrapper, args=(point, hold_duration, q))
        t2 = threading.Thread(target=self.jit_read_wrapper, args=(self.read_from_controller, q))
        # start threads and join them so this main thread waits for them to finish
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # return Queue[1], which is the touch controller's data
        ans1 = q.get_nowait()
        ans2 = q.get_nowait()
        return ans2

    def jit_read_wrapper(self, rfc, q: queue.Queue):
        """
        wrapper method for the read
        :param rfc: read_from_controller() method
        :param q: queue
        :return: N/A
        """
        q.put(rfc())

    def jit_move_wrapper(self, point, hold_duration, q: queue.Queue):
        """
        move wrapper for the jitter touch test
        :param point: point being evaluated
        :param hold_duration: how long to hold down
        :param q: queue
        :return: N/A
        """
        q.put(self.jitter_touch(point, hold_duration))

    ####
    # SNR Methods

    def run_snr_test(self, is_large_read=False, debug=False):
        """
        runs the SNR test
        :param is_large_read:
        :param debug: bool determining if the debug data is output
        :return: core and edge SNR values
        """
        # FORMULA:
        # note: this formula does not have the touch finger contacting the screen
        # noise = max(input got from controller) - min(input got from controller)
        # then ,take same number of data points, get the average of this and the average from the
        # data points gotten in the noise calculation.
        # Noise = max(not touching input) - min(not touching input
        # Signal = avg(not touching) - avg(touching)
        # SNR = Signal/Noise
        core_snr_values = list()
        edge_snr_values = list()

        is_core = True

        for test in [self._dxf_reader.get_snr_core(), self._dxf_reader.get_snr_edge()]:
            # iterate over each touch_point from the dxf file
            for touch_point in test:
                # get x and y coordinate from touch point
                x_pt = touch_point[0]
                y_pt = touch_point[1]

                x_node, y_node = self.snr_get_node_numbers(x_pt, y_pt)
                # get noises around given x,y point
                noises = self.snr_noise_test(x_pt, y_pt, x_node=x_node, y_node=y_node, large_read=is_large_read)
                # get signals around given x,y point
                signals = self.snr_signal_test(x_pt, y_pt, noises, x_node=x_node, y_node=y_node)
                snr_values = list()

                # move finger off of board
                self.robot_controller.move(x_pt, y_pt, self._z_start - Z_OFFSET)

                # calculate SNR for each index of the signals and noises
                for i in range(len(signals)):
                    if noises[i] != 0:
                        snr_values.append(signals[i] / noises[i])
                    else:
                        snr_values.append(0)
                if debug:
                    print("Max SNR VALUE: " + str(max(snr_values)) + '\n')
                # get touch coordinates centered to match the board
                centered_point = self.convert_robot_to_screen_coordinates(touch_point['x'], touch_point['y'])
                # append snr value to core data

                max_snr = max(snr_values)
                raw_data = (self.snr_figure_nodes(x_node, y_node, is_large_read=is_large_read), signals, noises)
                if is_core:
                    core_snr_values.append([centered_point, max_snr, raw_data])
                else:
                    edge_snr_values.append([centered_point, max_snr, raw_data])
            is_core = False
        return core_snr_values, edge_snr_values

    def snr_signal_test(self, x: float, y: float, noises: list, x_node=None, y_node=None, debug=False):
        """
        gets the signal from a point on the screen
        :param y_node:
        :param x_node:
        :param x: X coordinate of the signal
        :param y: Y coordinate of the signal
        :param noises: list of noises of same points being tested by the signal test
        :param debug: bool determining if debug data is output to console
        :return: list of signals
        """
        is_large_read = len(noises) == 25
        # make sure noises is len(9)
        if not is_large_read and len(noises) != 9:
            raise errors.InvalidInput('The noises parameter is ' + str(len(noises)) + ' in size, but needs to be 9 '
                                                                                      ' or 25 in size.')
        # check to make sure data passed into method is correct
        elif x_node is not None or y_node is not None:
            if type(x_node) is not int:
                raise ValueError("x_node is a " + str(type(x_node)) + " but needs to be an int.")
            elif type(y_node) is not int:
                raise ValueError("y_node is a " + str(type(y_node)) + " but needs to be an int.")
        # move finger onto board
        self.robot_controller.move(x, y, self._z_start)
        if x_node is None or y_node is None:
            x_node, y_node = self.snr_get_node_numbers(x, y)
        if debug:
            print("X NODE: " + str(x_node))
            print("Y NODE: " + str(y_node))
            print("##########################")

        # get signal samples
        if is_large_read:
            deltas = self.touch_controller.twenty_five_point_read(x_node, y_node, self._snr_num_signal_samples,
                                                                       sleep_sec=self._snr_sec_between_touch)
        else:
            deltas = self.touch_controller.nine_point_read(x_node, y_node, self._snr_num_signal_samples,
                                                                sleep_sec=self._snr_sec_between_touch)
        self.robot_controller.move(x, y, self._z_start - Z_OFFSET)  # move finger off of board
        signals = list()
        index = 0

        for node_deltas in deltas:
            average_delta = 0
            # get average delta value
            for delta in node_deltas:
                average_delta += delta
            average_delta /= len(node_deltas)
            # signal = average(finger on board) - average(finger not on board)
            signals.append(average_delta - noises[index])
            index += 1
        return signals

    def snr_noise_test(self, x: float, y: float, large_read=True, x_node=None, y_node=None, debug=False):
        """
        performs a noise test for SNR
        :param y_node:
        :param x_node:
        :param x: X coordinate to test
        :param y: Y coordinate to test
        :param large_read: bool representing if a large run is performed
        :param debug: bool determining if debug data is output
        :return: list of noise values
        """

        # check to make sure data passed into method is correct
        if x_node is not None or y_node is not None:
            if type(x_node) is not int:
                raise ValueError("x_node is a " + str(type(x_node)) + " but needs to be an int.")
            elif type(y_node) is not int:
                raise ValueError("y_node is a " + str(type(y_node)) + " but needs to be an int.")
        else:
            x_node, y_node = self.snr_get_node_numbers(x, y)

        # move finger above board
        self.robot_controller.move(x, y, self._z_start - Z_OFFSET, is_continuous=False)

        if debug:
            print("X NODE: " + str(x_node))
            print("Y NODE: " + str(y_node))

        # get noise samples
        if large_read:
            deltas = self.touch_controller.twenty_five_point_read(x_node, y_node, self._snr_num_noise_samples,
                                                                      sleep_sec=self._snr_sec_between_touch)
        else:
            deltas = self.touch_controller.nine_point_read(x_node, y_node, self._snr_num_noise_samples,
                                                               sleep_sec=self._snr_sec_between_touch)

        noises = list()
        # get the noise for each node_data in deltas
        for node_data in deltas:
            noises.append(max(node_data) - min(node_data))
        # return noise = max(Nnf) - min(Nnf)
        return noises

    def snr_get_node_numbers(self, x, y):
        """
        gets the node numbers to evaluate for a given X,Y coordinate pair
        :param x: X coordinate
        :param y: Y coordinate
        :return: x node, y node
        """
        # determine orientation of the axes
        nodal_origin = self._dxf_reader.get_nodal_origin()
        pos_x = self._dxf_reader.get_nodal_x_direction()
        # determine the distances between each node
        y_len = self._dxf_reader.get_y_node_line().get_length()
        x_len = self._dxf_reader.get_x_node_line().get_length()

        num_x_nodes = self._num_x_nodes - 1
        num_y_nodes = self._num_y_nodes - 1

        if are_nums_close(nodal_origin['y'], pos_x['y'], closeness=2) and not \
                are_nums_close(nodal_origin['x'], pos_x['x'], closeness=2):  # CASE 1: pos_x along robot x axis
            x_dist = abs(nodal_origin['x'] - x)
            y_dist = abs(nodal_origin['y'] - y)
        elif are_nums_close(nodal_origin['x'], pos_x['x'], closeness=2) and not \
                are_nums_close(nodal_origin['y'], pos_x['y'], closeness=2):  # CASE 2: pos_x along robot y axis
            x_dist = abs(nodal_origin['y'] - y)
            y_dist = abs(nodal_origin['x'] - x)
        else:
            raise ImportError("Nodal lines on DXF file are not properly made.")

        y_node_distance = y_len / num_y_nodes
        x_node_distance = x_len / num_x_nodes

        x_node = int(round(x_dist / x_node_distance, 0))
        y_node = int(round(y_dist / y_node_distance, 0))
        return x_node, y_node

    def snr_figure_nodes(self, xn, yn, is_large_read=True):
        """
        returns a matrix of nodes representing the nodes of the capacitive touch screen that were analyzed
        :param xn: X node examined
        :param yn: Y node examined
        :param is_large_read: bool that determines if the controller examines 9 (False) nodes or 25 (True)
        :return: matrix of examined nodes
        """
        if is_large_read:
            # handle edge cases
            xn = 2 if xn - 2 < 0 else xn
            xn = self._num_x_nodes - 2 if xn + 2 > self._num_x_nodes else xn
            yn = 2 if yn - 2 < 0 else yn
            yn = self._num_y_nodes - 2 if yn + 2 > self._num_x_nodes else yn

            return [(xn - 2, yn - 2), (xn - 1, yn - 2), (xn, yn - 2), (xn + 1, yn - 2), (xn + 2, yn - 2),
                    (xn - 2, yn - 1), (xn - 1, yn - 1), (xn, yn - 1), (xn + 1, yn - 1), (xn + 2, yn - 1),
                    (xn - 2, yn),     (xn - 1, yn),     (xn, yn),     (xn + 1, yn),     (xn + 2, yn),
                    (xn - 2, yn + 1), (xn - 1, yn + 1), (xn, yn + 1), (xn + 1, yn + 1), (xn + 2, yn + 1),
                    (xn - 2, yn + 2), (xn - 1, yn + 2), (xn, yn + 2), (xn + 1, yn + 2), (xn + 2, yn + 2)]
        else:
            # handle edge cases
            xn = 1 if xn - 1 < 0 else xn
            xn = self._num_x_nodes - 2 if xn + 1 > self._num_x_nodes else xn
            yn = 1 if yn - 1 < 0 else yn
            yn = self._num_y_nodes - 2 if yn + 1 > self._num_x_nodes else yn

            return [(xn - 1, yn - 1), (xn, yn - 1), (xn + 1, yn - 1),
                    (xn - 1, yn),     (xn, yn),     (xn + 1, yn),
                    (xn - 1, yn + 1), (xn, yn + 1), (xn + 1, yn + 1)]

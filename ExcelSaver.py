import math
import os

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import pandas as pd
import xlwt

import errors
from DXFReader import Point
from PIL import Image
import pdb


class ExcelSaver:

    def __init__(self, filepath: str, acc_params: list, snr_params: list, jit_params: list, lin_params: list,
                 num_x_nodes: int, num_y_nodes: int, acc_results=None, snr_results=None, jit_results=None,
                 lin_results=None, sensor_data=None, conversion_function=None):
        """
        Saves the test data to an excel file.
        Object is disregarded after saving

        :param filepath: string of the filepath to save to
        :param acc_params: parameters for the accuracy test
        :param snr_params: parameters for the snr test
        :param jit_params: parameters for the jitter test
        :param lin_params: parameters for the linearity test
        :param num_x_nodes: number of X nodes on the screen
        :param num_y_nodes: number of y nodes on the screen
        :param acc_results: accuracy results from test manager
        :param snr_results: snr results from test manager
        :param jit_results: jitter results from test manager
        :param lin_results: linearity results from test manager
        :param sensor_data: sensor related data
        :param conversion_function: function used to convert from robot to screen coordinates

        :return: None
        """

        # make sure certain parameters that are passed in are correct
        if len(acc_params) != 7 or len(snr_params) != 7 or len(jit_params) != 7 or len(lin_params) != 6 or \
                conversion_function is None:
            raise errors.SaveError("Parameters are not the correct size")

        # set up fail style
        self.fail_style = xlwt.XFStyle()
        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['red']
        self.fail_style.pattern = pattern

        # set up bold style
        self.bold_style = xlwt.XFStyle()
        font = xlwt.Font()
        font.bold = True
        self.bold_style.font = font

        book = xlwt.Workbook()

        # write accuracy results to excel
        if acc_results:
            self.save_acc(book, acc_results, acc_params[5], acc_params[6])

        # write jitter results to excel
        if jit_results:
            self.save_jit(book, jit_results, jit_params[5], jit_params[6])

        # write linearity results to excel
        if lin_results:
            self.save_lin(book, lin_results, lin_params[4], lin_params[5], function=conversion_function)

        # write snr results to excel
        if snr_results:
            self.save_snr(book, snr_results, snr_params[5], snr_params[6], num_x_nodes, num_y_nodes)

        self.save_final_sheet(book, acc_params=acc_params, snr_params=snr_params, jit_params=jit_params,
                              lin_params=lin_params, sensor_data=sensor_data)

        book.save(filepath)

    def save_acc(self, book: xlwt.Workbook, accuracy_results: list, core_pf, edge_pf) -> None:
        """
        Saves accuracy data to an Excel workbook

        :param book: xlwt book to save to
        :param accuracy_results: results of accuracy test
        :param core_pf: core pass/fail conditions
        :param edge_pf: edge pass/fail conditions

        :return:
        """
        # self._acc_results:
        #   0: core results
        #   1: edge results
        #   2: full results

        accuracy_sheet = book.add_sheet("Accuracy Results")
        accuracy_labels_row = accuracy_sheet.row(1)
        acc_data_labels_row = accuracy_sheet.row(2)

        # set up layout for Accuracy
        accuracy_labels_row.write(1, "Accuracy:", style=self.bold_style)
        acc_data_labels_row.write(1, "X Coord", style=self.bold_style)
        acc_data_labels_row.write(2, "Y Coord", style=self.bold_style)
        current_row_num = 3

        edge_accuracy_values = list()
        core_accuracy_values = list()

        final_core_values = list()
        final_edge_values = list()
        final_full_values = list()

        iterations = 0

        for accuracy_result in accuracy_results:
            part_name = accuracy_result[-1]
            # this block iterates over all core values to get each accuracy value appended to the list
            # of core accuracy values (this is for the final table output)
            for test_ran in accuracy_result[0]:  # for each test ran in the core of the screen
                for iteration in test_ran:  # for each iteration of the test ran in the core tests that were run
                    # for each list of [point, (accuracy values)] in the test iteration
                    for accuracy in iteration[1]:
                        core_accuracy_values.append(accuracy)

            # this block iterates over all edge values to get each accuracy value appended to the list
            # of core accuracy values (this is for the final table output)
            for test_ran in accuracy_result[1]:  # for each test ran in the core of the screen
                for iteration in test_ran:  # for each iteration of the test ran in the core tests that were run
                    # for each list of [point, (accuracy values)] in the test iteration
                    for accuracy in iteration[1]:
                        edge_accuracy_values.append(accuracy)

            all_core_values = accuracy_result[0]
            all_edge_values = accuracy_result[1]
            all_full_values = accuracy_result[2]

            # set column width where they need to be increased:
            # 1 unit in xlwt is 256, so these will have a width of 14
            accuracy_sheet.col(15 + len(all_full_values[0][0][1])).width = 256 * 14
            accuracy_sheet.col(24 + len(all_full_values[0][0][1])).width = 256 * 14

            full_accuracy_values = list()

            # write out test iterations (number of touches per point)
            if iterations == 0:
                for test_num in range(len(all_full_values[0][0][1])):
                    acc_data_labels_row.write(3 + test_num, "Touch: " + str(test_num + 1), style=self.bold_style)

            graph_col = 4 + len(all_full_values[0][0][1])
            table_col = graph_col + 11
            final_table_col = table_col + 9
            raw_data_col = final_table_col + 9 + ((11 * len(accuracy_result[0])) * iterations)

            # write where raw data begins
            if iterations == 0:
                accuracy_sheet.row(1).write(raw_data_col, "Raw Data:", style=self.bold_style)

            for i in range(len(all_full_values)):
                # set up accuracy graph
                fig, ax = plt.subplots()
                img_title = "Accuracy Test " + part_name + ", Iteration " + str(i + 1)
                ax.set(xlabel="X - Axis (mm)", ylabel="Y - Axis (mm)", title=img_title)
                start_row = current_row_num  # save the start row of the test

                # write table's
                accuracy_sheet.row(start_row - 1).write(table_col, part_name + " Table:", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col, "Parameter", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 1, "Min", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 2, "Average", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 3, "Max", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 4, "Units", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 5, "Expected", style=self.bold_style)
                accuracy_sheet.row(start_row).write(table_col + 6, "Units", style=self.bold_style)

                accuracy_sheet.row(current_row_num).write(1, part_name + ":", style=self.bold_style)
                current_row_num += 1
                accuracy_sheet.row(current_row_num).write(1, "Core:", style=self.bold_style)
                current_row_num += 1
                # initialize lists for table output (the one for this specific test iteration)
                core_acc_table_data = list()
                edge_acc_table_data = list()
                full_acc_table_data = list()

                # write header of raw data output
                raw_data_header = 3
                accuracy_sheet.row(raw_data_header - 1).write(raw_data_col, part_name + " Core " + str(i + 1) + ":", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col, "X:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 1, "Y:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 2, "X ERR:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 3, "Y ERR:", style=self.bold_style)

                accuracy_sheet.row(raw_data_header - 1).write(raw_data_col + 5, part_name + " Edge " + str(i + 1) + ":",
                                                              style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 5, "X:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 6, "Y:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 7, "X ERR:", style=self.bold_style)
                accuracy_sheet.row(raw_data_header).write(raw_data_col + 8, "Y ERR:", style=self.bold_style)

                acc_position_raw_data_row = raw_data_header + 1  # initialize acc_position_raw_data_row
                acc_errors_raw_data_row = raw_data_header + 1  # initialize acc_errors_raw_data_row

                # iterate over all core values
                for test_results_core in all_core_values[i]:
                    # write each line of data to excel
                    count = 0
                    for data in test_results_core:
                        # this section writes the X and Y coordinate to XL
                        current_row = accuracy_sheet.row(current_row_num)

                        if type(data) is Point:
                            count += 1
                            current_row.write(1, data['x'])  # write X coordinate
                            current_row.write(2, data['y'])  # write Y coordinate
                            plt.plot(data['x'], data['y'], marker='x', color='blue', markersize=3)
                        elif count == 1:
                            count += 1
                            current_col_num = 3
                            for acc_val in data:
                                if acc_val > core_pf:
                                    current_row.write(current_col_num, round(acc_val, 3), style=self.fail_style)
                                else:
                                    current_row.write(current_col_num, round(acc_val, 3))
                                full_accuracy_values.append(acc_val)
                                core_acc_table_data.append(acc_val)
                                full_acc_table_data.append(acc_val)
                                final_core_values.append(acc_val)
                                final_full_values.append(acc_val)
                                current_col_num += 1
                        elif count == 2:  # case of actual points tested
                            count += 1
                            for location in data:
                                # write points on graph and raw output
                                accuracy_sheet.row(acc_position_raw_data_row).write(raw_data_col, location[0])
                                accuracy_sheet.row(acc_position_raw_data_row).write(raw_data_col + 1, location[1])
                                plt.plot(location[0], location[1], marker='o', color='black', markersize=3)
                                acc_position_raw_data_row += 1
                            acc_position_raw_data_row += 1
                        elif count == 3:  # case of errors calculated
                            count += 1
                            for errs in data:
                                accuracy_sheet.row(acc_errors_raw_data_row).write(raw_data_col + 2, errs[0])
                                accuracy_sheet.row(acc_errors_raw_data_row).write(raw_data_col + 3, errs[1])
                                acc_errors_raw_data_row += 1
                            acc_errors_raw_data_row += 1

                    current_row_num += 1
                current_row_num += 2  # add skip between different tests

                accuracy_sheet.row(current_row_num).write(1, "Edge:", style=self.bold_style)
                current_row_num += 1

                acc_position_raw_data_row = raw_data_header + 1  # initialize acc_position_raw_data_row
                acc_errors_raw_data_row = raw_data_header + 1  # initialize acc_errors_raw_data_row

                # iterate over all edge values
                for test_results_edge in all_edge_values[i]:
                    # write each line of data to excel
                    count = 0
                    for data in test_results_edge:
                        # this section writes the X and Y coordinate to XL
                        current_row = accuracy_sheet.row(current_row_num)

                        if type(data) is Point:
                            count += 1
                            current_row.write(1, data['x'])  # write X coordinate
                            current_row.write(2, data['y'])  # write Y coordinate
                            plt.plot(data['x'], data['y'], marker='x', color='red', markersize=3)
                        elif count == 1:
                            count += 1
                            current_col_num = 3
                            for acc_val in data:
                                if acc_val > edge_pf:
                                    current_row.write(current_col_num, round(acc_val, 3), style=self.fail_style)
                                else:
                                    current_row.write(current_col_num, round(acc_val, 3))
                                full_accuracy_values.append(acc_val)
                                edge_acc_table_data.append(acc_val)
                                full_acc_table_data.append(acc_val)
                                final_full_values.append(acc_val)
                                final_edge_values.append(acc_val)
                                current_col_num += 1
                        elif count == 2:  # case of actual points tested
                            count += 1
                            for location in data:
                                # write points on graph and raw output
                                accuracy_sheet.row(acc_position_raw_data_row).write(raw_data_col + 5, location[0])
                                accuracy_sheet.row(acc_position_raw_data_row).write(raw_data_col + 6, location[1])
                                plt.plot(location[0], location[1], marker='o', color='black', markersize=3)
                                acc_position_raw_data_row += 1
                            acc_position_raw_data_row += 1
                        elif count == 3:  # case of errors calculated
                            count += 1
                            for errs in data:
                                accuracy_sheet.row(acc_errors_raw_data_row).write(raw_data_col + 7, errs[0])
                                accuracy_sheet.row(acc_errors_raw_data_row).write(raw_data_col + 8, errs[1])
                                acc_errors_raw_data_row += 1
                            acc_errors_raw_data_row += 1

                    current_row_num += 1

                raw_data_col += 11

                # print rest of current test's table
                # Accuracy Full layer
                accuracy_sheet.row(start_row + 1).write(table_col, "Accuracy Full")
                accuracy_sheet.row(start_row + 1).write(table_col + 1, min(full_acc_table_data))
                accuracy_sheet.row(start_row + 1).write(table_col + 2,
                                                        sum(full_acc_table_data) / len(full_acc_table_data))
                accuracy_sheet.row(start_row + 1).write(table_col + 3, max(full_acc_table_data))
                accuracy_sheet.row(start_row + 1).write(table_col + 4, "mm")
                accuracy_sheet.row(start_row + 1).write(table_col + 5, edge_pf)
                accuracy_sheet.row(start_row + 1).write(table_col + 6, "mm")

                # Accuracy Core layer
                accuracy_sheet.row(start_row + 2).write(table_col, "Accuracy Core")
                accuracy_sheet.row(start_row + 2).write(table_col + 1, min(core_acc_table_data))
                accuracy_sheet.row(start_row + 2).write(table_col + 2,
                                                        (sum(core_acc_table_data) / len(core_acc_table_data)))
                accuracy_sheet.row(start_row + 2).write(table_col + 3, max(core_acc_table_data))
                accuracy_sheet.row(start_row + 2).write(table_col + 4, "mm")
                accuracy_sheet.row(start_row + 2).write(table_col + 5, core_pf)
                accuracy_sheet.row(start_row + 2).write(table_col + 6, "mm")

                # Accuracy Edge layer
                accuracy_sheet.row(start_row + 3).write(table_col, "Accuracy Edge")
                accuracy_sheet.row(start_row + 3).write(table_col + 1, min(edge_acc_table_data))
                accuracy_sheet.row(start_row + 3).write(table_col + 2,
                                                        (sum(edge_acc_table_data) / len(edge_acc_table_data)))
                accuracy_sheet.row(start_row + 3).write(table_col + 3, max(edge_acc_table_data))
                accuracy_sheet.row(start_row + 3).write(table_col + 4, "mm")
                accuracy_sheet.row(start_row + 3).write(table_col + 5, edge_pf)
                accuracy_sheet.row(start_row + 3).write(table_col + 6, "mm")

                # handle cases where graphs would overlap
                if current_row_num - start_row < 31:
                    current_row_num = start_row + 31

                # save the figure and name it
                plt.savefig(fname="acc_image.png", format='png')
                plt.close()  # close the figure when finished
                img = Image.open("acc_image.png")
                r, g, b, a = img.split()
                img = Image.merge("RGB", (r, g, b))
                img_name = 'acc_graph_for_excel_' + str(i + 1) + '.bmp'
                img.save(img_name)

                # insert image to excel
                accuracy_sheet.insert_bitmap("acc_graph_for_excel_" + str(i + 1) + ".bmp", start_row, graph_col)
                current_row_num += 2  # add skip between different tests
            iterations += 1
        # write final data table below

        # top layer outline
        accuracy_sheet.row(0).write(final_table_col, "Overall:", style=self.bold_style)
        accuracy_labels_row.write(final_table_col, "Parameter", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 1, "Min", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 2, "Average", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 3, "Max", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 4, "Units", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 5, "Expected", style=self.bold_style)
        accuracy_labels_row.write(final_table_col + 6, "Units", style=self.bold_style)

        # Accuracy Full layer
        acc_data_labels_row.write(final_table_col, "Accuracy Full")
        acc_data_labels_row.write(final_table_col + 1, min(final_full_values))
        acc_data_labels_row.write(final_table_col + 2, sum(final_full_values) / len(final_full_values))
        acc_data_labels_row.write(final_table_col + 3, max(final_full_values))
        acc_data_labels_row.write(final_table_col + 4, "mm")
        acc_data_labels_row.write(final_table_col + 5, edge_pf)
        acc_data_labels_row.write(final_table_col + 6, "mm")

        # Accuracy Core layer
        acc_core_row = accuracy_sheet.row(3)
        acc_core_row.write(final_table_col, "Accuracy Core")
        acc_core_row.write(final_table_col + 1, min(final_core_values))
        acc_core_row.write(final_table_col + 2, (sum(final_core_values) / len(final_core_values)))
        acc_core_row.write(final_table_col + 3, max(final_core_values))
        acc_core_row.write(final_table_col + 4, "mm")
        acc_core_row.write(final_table_col + 5, core_pf)
        acc_core_row.write(final_table_col + 6, "mm")

        # Accuracy Edge layer
        acc_edge_row = accuracy_sheet.row(4)
        acc_edge_row.write(final_table_col, "Accuracy Edge")
        acc_edge_row.write(final_table_col + 1, min(final_edge_values))
        acc_edge_row.write(final_table_col + 2, (sum(final_edge_values) / len(final_edge_values)))
        acc_edge_row.write(final_table_col + 3, max(final_edge_values))
        acc_edge_row.write(final_table_col + 4, "mm")
        acc_edge_row.write(final_table_col + 5, edge_pf)
        acc_edge_row.write(final_table_col + 6, "mm")

        for i in range(1, len(accuracy_results[0][0]) + 1):
            os.remove("acc_graph_for_excel_" + str(i) + ".bmp")
        os.remove("acc_image.png")

    def save_jit(self, book: xlwt.Workbook, jitter_results, core_pf, edge_pf) -> None:
        """
        Saves jitter data to an Excel workbook

        :param book: xlwt book to save to
        :param jitter_results: results of the jitter test
        :param core_pf: pass/fail condition for the core
        :param edge_pf: pass/fail condition for the edge
        :return: N/A
        """
        # self._jit_results:
        #   0: core
        #   1: edge
        #   2: full

        labels_row = 1

        jitter_sheet = book.add_sheet("Jitter Results")
        jitter_labels_row = jitter_sheet.row(labels_row)
        jitter_data_labels_row = jitter_sheet.row(2)

        # set column lengths that need to be bigger to fit data
        jitter_sheet.col(7).width = 256 * 11
        jitter_sheet.col(16).width = 256 * 11

        # set up layout for Jitter
        jitter_labels_row.write(1, "Jitter:", style=self.bold_style)
        jitter_data_labels_row.write(1, "X Coord", style=self.bold_style)
        jitter_data_labels_row.write(2, "Y Coord", style=self.bold_style)
        jitter_data_labels_row.write(3, "Jitter X", style=self.bold_style)
        jitter_data_labels_row.write(4, "Jitter Y", style=self.bold_style)

        full_jit_x = list()
        full_jit_y = list()
        core_jit_x = list()
        core_jit_y = list()
        edge_jit_x = list()
        edge_jit_y = list()

        current_row_num = 3
        graph_col = 15
        raw_data_col = 36
        single_test_graph_col = 7

        for jitter_result in jitter_results:

            part_name = jitter_result[-1]

            for i in range(len(jitter_result[0])):  # do this the number of times the test was run
                core_data = jitter_result[0][i]
                edge_data = jitter_result[1][i]

                # core/edge data outline: each index of this list is a tuple with 3 indicies
                # 0: the point object that was tested
                # 1: A tuple with the format (jitter_x, jitter_y)
                # 2: all the registered points (used for raw data output to excel)

                jitter_sheet.insert_bitmap("jit_graph_for_excel_" + part_name + str(i + 1) + ".bmp",
                                           current_row_num, graph_col)
                os.remove("jit_graph_for_excel_" + part_name + str(i + 1) + ".bmp")
                jitter_sheet.row(current_row_num).write(1, "Iteration " + str(i + 1) + ":", style=self.bold_style)
                current_row_num += 1
                jitter_sheet.row(current_row_num).write(1, part_name + " Core:", style=self.bold_style)
                graph_row_num = current_row_num
                start_row_num = current_row_num
                current_row_num += 1

                param_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 1

                # write date table below
                param_row.write(single_test_graph_col, "Parameter", style=self.bold_style)
                param_row.write(single_test_graph_col + 1, "Min", style=self.bold_style)
                param_row.write(single_test_graph_col + 2, "Average", style=self.bold_style)
                param_row.write(single_test_graph_col + 3, "Max", style=self.bold_style)
                param_row.write(single_test_graph_col + 4, "Units", style=self.bold_style)
                param_row.write(single_test_graph_col + 5, "Expected", style=self.bold_style)
                param_row.write(single_test_graph_col + 6, "Units", style=self.bold_style)

                # initialize lists for unit test graph data
                core_x_iteration_data = list()
                core_y_iteration_data = list()
                edge_x_iteration_data = list()
                edge_y_iteration_data = list()
                full_x_iteration_data = list()
                full_y_iteration_data = list()
                core_x_iteration_data.clear()
                core_y_iteration_data.clear()
                edge_x_iteration_data.clear()
                edge_y_iteration_data.clear()
                full_x_iteration_data.clear()
                full_y_iteration_data.clear()

                core_to_append_x = [core_jit_x, full_jit_x, core_x_iteration_data, full_x_iteration_data]
                core_to_append_y = [core_jit_y, full_jit_y, core_y_iteration_data, full_y_iteration_data]
                edge_to_append_x = [edge_jit_x, full_jit_x, edge_x_iteration_data, full_x_iteration_data]
                edge_to_append_y = [edge_jit_y, full_jit_y, edge_y_iteration_data, full_y_iteration_data]

                # iterate over all core data
                for core_point_data in core_data:
                    test_location = core_point_data[0]  # get point of test location
                    jitter_tuple = core_point_data[1]  # get tuple of jitters
                    jitter_x = jitter_tuple[0]  # get X jitter
                    jitter_y = jitter_tuple[1]  # get Y jitter

                    # append value to all lists that require it
                    for ls in core_to_append_x:
                        ls.append(jitter_x)
                    for ls in core_to_append_y:
                        ls.append(jitter_y)

                    row = jitter_sheet.row(current_row_num)  # get next row
                    row.write(1, test_location['x'])  # write x coordinate of test location
                    row.write(2, test_location['y'])  # write y coordinate of test location
                    if jitter_x > core_pf:
                        row.write(3, jitter_x, style=self.fail_style)  # write jitter x with fail style
                    else:
                        row.write(3, jitter_x)  # write jitter x
                    if jitter_y > core_pf:
                        row.write(4, jitter_y, style=self.fail_style)  # write jitter y with fail style
                    else:
                        row.write(4, jitter_y)  # write jitter y
                    current_row_num += 1  # increment row
                current_row_num += 2

                # print core data to excel
                jitter_sheet.row(graph_row_num).write(single_test_graph_col, part_name + " Core:",
                                                      style=self.bold_style)
                graph_row_num += 1
                core_x_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 1
                # Jitter X Core layer
                core_x_row.write(single_test_graph_col, "Jitter X")
                core_x_row.write(single_test_graph_col + 1, min(core_x_iteration_data))
                core_x_row.write(single_test_graph_col + 2, sum(core_x_iteration_data) / len(core_x_iteration_data))
                core_x_row.write(single_test_graph_col + 3, max(core_x_iteration_data))
                core_x_row.write(single_test_graph_col + 4, "mm")
                core_x_row.write(single_test_graph_col + 5, core_pf)
                core_x_row.write(single_test_graph_col + 6, "mm")

                core_y_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 2

                # Jitter Y Core layer
                core_y_row.write(single_test_graph_col, "Jitter Y")
                core_y_row.write(single_test_graph_col + 1, min(core_y_iteration_data))
                core_y_row.write(single_test_graph_col + 2, sum(core_y_iteration_data) / len(core_y_iteration_data))
                core_y_row.write(single_test_graph_col + 3, max(core_y_iteration_data))
                core_y_row.write(single_test_graph_col + 4, "mm")
                core_y_row.write(single_test_graph_col + 5, core_pf)
                core_y_row.write(single_test_graph_col + 6, "mm")

                # write edge to start edge data
                jitter_sheet.row(current_row_num).write(1, part_name + " Edge:", style=self.bold_style)
                current_row_num += 1

                for edge_point_data in edge_data:
                    test_location = edge_point_data[0]  # get point of test location
                    jitter_tuple = edge_point_data[1]  # get tuple of jitters
                    jitter_x = jitter_tuple[0]  # get X jitter
                    jitter_y = jitter_tuple[1]  # get Y jitter

                    # append value to all lists that require it
                    for ls in edge_to_append_x:
                        ls.append(jitter_x)
                    for ls in edge_to_append_y:
                        ls.append(jitter_y)

                    row = jitter_sheet.row(current_row_num)  # get next row
                    row.write(1, test_location['x'])  # write x coordinate of test location
                    row.write(2, test_location['y'])  # write y coordinate of test location
                    if jitter_x > edge_pf:
                        row.write(3, jitter_x, style=self.fail_style)  # write jitter x with fail style
                    else:
                        row.write(3, jitter_x)  # write jitter x
                    if jitter_y > edge_pf:
                        row.write(4, jitter_y, style=self.fail_style)  # write jitter y with fail style
                    else:
                        row.write(4, jitter_y)  # write jitter y
                    current_row_num += 1  # increment row
                current_row_num += 2

                # print core data to excel
                jitter_sheet.row(graph_row_num).write(single_test_graph_col, part_name + " Edge:",
                                                      style=self.bold_style)
                graph_row_num += 1
                edge_x_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 1

                # Jitter X Edge layer
                edge_x_row.write(single_test_graph_col, "Jitter X")
                edge_x_row.write(single_test_graph_col + 1, min(edge_x_iteration_data))
                edge_x_row.write(single_test_graph_col + 2, sum(edge_x_iteration_data) / len(edge_x_iteration_data))
                edge_x_row.write(single_test_graph_col + 3, max(edge_x_iteration_data))
                edge_x_row.write(single_test_graph_col + 4, "mm")
                edge_x_row.write(single_test_graph_col + 5, edge_pf)
                edge_x_row.write(single_test_graph_col + 6, "mm")

                edge_y_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 2

                # Jitter Y Edge layer
                edge_y_row.write(single_test_graph_col, "Jitter Y")
                edge_y_row.write(single_test_graph_col + 1, min(edge_y_iteration_data))
                edge_y_row.write(single_test_graph_col + 2, sum(edge_y_iteration_data) / len(edge_y_iteration_data))
                edge_y_row.write(single_test_graph_col + 3, max(edge_y_iteration_data))
                edge_y_row.write(single_test_graph_col + 4, "mm")
                edge_y_row.write(single_test_graph_col + 5, edge_pf)
                edge_y_row.write(single_test_graph_col + 6, "mm")

                # print core data to excel
                jitter_sheet.row(graph_row_num).write(single_test_graph_col, part_name + " Full:",
                                                      style=self.bold_style)
                graph_row_num += 1
                full_x_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 1
                # Jitter X Edge layer
                full_x_row.write(single_test_graph_col, "Jitter X")
                full_x_row.write(single_test_graph_col + 1, min(full_x_iteration_data))
                full_x_row.write(single_test_graph_col + 2, sum(full_x_iteration_data) / len(full_x_iteration_data))
                full_x_row.write(single_test_graph_col + 3, max(full_x_iteration_data))
                full_x_row.write(single_test_graph_col + 4, "mm")
                full_x_row.write(single_test_graph_col + 5, edge_pf)
                full_x_row.write(single_test_graph_col + 6, "mm")

                full_y_row = jitter_sheet.row(graph_row_num)
                graph_row_num += 2

                # Jitter Y Edge layer
                full_y_row.write(single_test_graph_col, "Jitter Y")
                full_y_row.write(single_test_graph_col + 1, min(full_y_iteration_data))
                full_y_row.write(single_test_graph_col + 2, sum(full_y_iteration_data) / len(full_y_iteration_data))
                full_y_row.write(single_test_graph_col + 3, max(full_y_iteration_data))
                full_y_row.write(single_test_graph_col + 4, "mm")
                full_y_row.write(single_test_graph_col + 5, edge_pf)
                full_y_row.write(single_test_graph_col + 6, "mm")

                # write raw data output

                jitter_sheet.row(1).write(raw_data_col + 1, part_name + " Core:", style=self.bold_style)
                jitter_sheet.row(2).write(raw_data_col + 1, "X:", style=self.bold_style)
                jitter_sheet.row(2).write(raw_data_col + 2, "Y:", style=self.bold_style)

                row_num = 2
                jitter_sheet.row(row_num).write(raw_data_col, "Iteration " + str(i + 1) + ":", style=self.bold_style)
                jitter_sheet.col(raw_data_col).width = 256 * 12
                row_num += 1

                #########################
                # START RAW DATA OUTPUT #
                #########################

                # output all raw data to graph
                for core_pt_info in core_data:
                    jitter_sheet.row(row_num).write(raw_data_col, "Real Point:", style=self.bold_style)
                    # write out each point read
                    for pt in core_pt_info[2]:
                        jitter_sheet.row(row_num).write(raw_data_col + 1, pt['x'])
                        jitter_sheet.row(row_num).write(raw_data_col + 2, pt['y'])
                        row_num += 1
                    row_num += 1
                # reset row_num and iterate raw_data_column
                row_num = 3
                raw_data_col += 4

                # write header for raw edge data
                jitter_sheet.row(1).write(raw_data_col + 1, part_name + " Edge:", style=self.bold_style)
                jitter_sheet.row(2).write(raw_data_col + 1, "X:", style=self.bold_style)
                jitter_sheet.row(2).write(raw_data_col + 2, "Y:", style=self.bold_style)
                jitter_sheet.col(raw_data_col).width = 256 * 12

                # iterate over all edge points for raw data output
                for edge_pt_info in edge_data:
                    jitter_sheet.row(row_num).write(raw_data_col, "Real Point:", style=self.bold_style)
                    # write out each point read
                    for pt in edge_pt_info[2]:
                        jitter_sheet.row(row_num).write(raw_data_col + 1, pt['x'])
                        jitter_sheet.row(row_num).write(raw_data_col + 2, pt['y'])
                        row_num += 1
                    row_num += 1
                raw_data_col += 5  # iterate raw_data_column

                # handle case where image graph overlaps
                if current_row_num - start_row_num < 30:
                    current_row_num = start_row_num + 30
            current_row_num += 20


        #######################
        # END RAW DATA OUTPUT #
        #######################

        final_graph_start_col = 27

        #
        # BEGIN FINAL TABLE
        #

        # top layer outline
        jitter_sheet.row(0).write(final_graph_start_col, "Overall", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col, "Parameter", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 1, "Min", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 2, "Average", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 3, "Max", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 4, "Units", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 5, "Expected", style=self.bold_style)
        jitter_labels_row.write(final_graph_start_col + 6, "Units", style=self.bold_style)

        current_row_num = labels_row + 1

        #############################################################
        # BEGIN CORE TABLE
        jitter_sheet.row(current_row_num).write(final_graph_start_col, "Core:", style=self.bold_style)
        current_row_num += 1
        jitter_x_core_row = jitter_sheet.row(current_row_num)
        current_row_num += 1

        # Jitter X Core layer
        jitter_x_core_row.write(final_graph_start_col, "Jitter X")
        jitter_x_core_row.write(final_graph_start_col + 1, min(core_jit_x))
        jitter_x_core_row.write(final_graph_start_col + 2, sum(core_jit_x) / len(core_jit_x))
        jitter_x_core_row.write(final_graph_start_col + 3, max(core_jit_x))
        jitter_x_core_row.write(final_graph_start_col + 4, "mm")
        jitter_x_core_row.write(final_graph_start_col + 5, core_pf)
        jitter_x_core_row.write(final_graph_start_col + 6, "mm")

        jitter_y_core_row = jitter_sheet.row(current_row_num)
        current_row_num += 2

        # Jitter Y Core layer
        jitter_y_core_row.write(final_graph_start_col, "Jitter Y")
        jitter_y_core_row.write(final_graph_start_col + 1, min(core_jit_y))
        jitter_y_core_row.write(final_graph_start_col + 2, sum(core_jit_y) / len(core_jit_y))
        jitter_y_core_row.write(final_graph_start_col + 3, max(core_jit_y))
        jitter_y_core_row.write(final_graph_start_col + 4, "mm")
        jitter_y_core_row.write(final_graph_start_col + 5, core_pf)
        jitter_y_core_row.write(final_graph_start_col + 6, "mm")

        ################################################################
        # BEGIN EDGE TABLE
        jitter_sheet.row(current_row_num).write(final_graph_start_col, "Edge:", style=self.bold_style)
        current_row_num += 1
        jitter_x_edge_row = jitter_sheet.row(current_row_num)
        current_row_num += 1

        # Jitter X Edge layer
        jitter_x_edge_row.write(final_graph_start_col, "Jitter X")
        jitter_x_edge_row.write(final_graph_start_col + 1, min(edge_jit_x))
        jitter_x_edge_row.write(final_graph_start_col + 2, sum(edge_jit_x) / len(edge_jit_x))
        jitter_x_edge_row.write(final_graph_start_col + 3, max(edge_jit_x))
        jitter_x_edge_row.write(final_graph_start_col + 4, "mm")
        jitter_x_edge_row.write(final_graph_start_col + 5, edge_pf)
        jitter_x_edge_row.write(final_graph_start_col + 6, "mm")

        jitter_y_edge_row = jitter_sheet.row(current_row_num)
        current_row_num += 2

        # Jitter Y Edge layer
        jitter_y_edge_row.write(final_graph_start_col, "Jitter Y")
        jitter_y_edge_row.write(final_graph_start_col + 1, min(edge_jit_y))
        jitter_y_edge_row.write(final_graph_start_col + 2, sum(edge_jit_y) / len(edge_jit_y))
        jitter_y_edge_row.write(final_graph_start_col + 3, max(edge_jit_y))
        jitter_y_edge_row.write(final_graph_start_col + 4, "mm")
        jitter_y_edge_row.write(final_graph_start_col + 5, edge_pf)
        jitter_y_edge_row.write(final_graph_start_col + 6, "mm")

        jitter_sheet.row(current_row_num).write(final_graph_start_col, "Full:", style=self.bold_style)
        current_row_num += 1
        jitter_x_full_row = jitter_sheet.row(current_row_num)
        current_row_num += 1

        # Jitter X Full layer
        jitter_x_full_row.write(final_graph_start_col, "Jitter X")
        jitter_x_full_row.write(final_graph_start_col + 1, min(full_jit_x))
        jitter_x_full_row.write(final_graph_start_col + 2, sum(full_jit_x) / len(full_jit_x))
        jitter_x_full_row.write(final_graph_start_col + 3, max(full_jit_x))
        jitter_x_full_row.write(final_graph_start_col + 4, "mm")
        jitter_x_full_row.write(final_graph_start_col + 5, edge_pf)
        jitter_x_full_row.write(final_graph_start_col + 6, "mm")

        jitter_y_full_row = jitter_sheet.row(current_row_num)
        current_row_num += 2

        # Jitter Y Full layer
        jitter_y_full_row.write(final_graph_start_col, "Jitter Y")
        jitter_y_full_row.write(final_graph_start_col + 1, min(full_jit_y))
        jitter_y_full_row.write(final_graph_start_col + 2, sum(full_jit_y) / len(full_jit_y))
        jitter_y_full_row.write(final_graph_start_col + 3, max(full_jit_y))
        jitter_y_full_row.write(final_graph_start_col + 4, "mm")
        jitter_y_full_row.write(final_graph_start_col + 5, edge_pf)
        jitter_y_full_row.write(final_graph_start_col + 6, "mm")

        os.remove("jit_image.png")

    def save_snr(self, book: xlwt.Workbook, snr_results, core_pf, edge_pf, num_x_nodes: int, num_y_nodes: int) -> None:
        """
        Saves SNR data to an Excel workbook

        :param book: xlwt book to save to
        :param snr_results: results of the SNR test
        :param core_pf: pass/fail condition of the core
        :param edge_pf: pass/fail condition of the edge
        :return: N/A
        """
        snr_sheet = book.add_sheet("SNR Results", cell_overwrite_ok=True)
        snr_labels_row = snr_sheet.row(1)
        snr_data_labels_row = snr_sheet.row(2)

        # set column width of columns that need to be set
        snr_sheet.col(29).width = 256 * 12
        snr_sheet.col(38).width = 256 * 12

        snr_labels_row.write(1, "SNR:", style=self.bold_style)
        snr_labels_row.write(45, "RAW DATA:", style=self.bold_style)  # head raw data
        snr_data_labels_row.write(1, "X Coord:", style=self.bold_style)
        snr_data_labels_row.write(2, "Y Coord:", style=self.bold_style)
        snr_data_labels_row.write(3, "SNR Calculated", style=self.bold_style)

        current_row_num = 3
        core_snr_values = list()
        core_snr_values.clear()
        edge_snr_values = list()
        edge_snr_values.clear()

        raw_data_col = 45
        raw_data_start_row = 2
        screen_iteration = 0

        for snr_result in snr_results:
            for test_iteration in range(len(snr_result[0])):
                part_name = snr_result[-1]
                points = list()
                points.clear()
                x_coordinates = list()
                y_coordinates = list()
                all_snr_values = list()
                current_edge_snr_values = list()
                current_core_snr_values = list()
                all_snr_values.clear()
                current_test_start_row = current_row_num
                snr_sheet.row(current_row_num).write(1, part_name + " Core, iteration: " + str(test_iteration + 1),
                                                     style=self.bold_style)
                current_row_num += 1

                snr_sheet.col(raw_data_col).width = 256 * 20
                snr_sheet.row(raw_data_start_row).write(raw_data_col, part_name + " Core:",
                                                        style=self.bold_style)
                snr_sheet.row(raw_data_start_row + 1).write(raw_data_col, "Iteration " + str(test_iteration + 1) + ":",
                                                            style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 1, "X", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 2, "Y", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 3, "X_NODE", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 4, "Y_NODE", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 5, "SIGNAL", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 6, "NOISE", style=self.bold_style)

                result_start_row = 1 + raw_data_start_row
                for core_result in snr_result[0][test_iteration]:
                    # iterate over the core results
                    current_row = snr_sheet.row(current_row_num)
                    current_row.write(1, core_result[0]['x'])  # write X coordinate
                    snr_sheet.row(result_start_row).write(raw_data_col + 1,
                                                          core_result[0]['x'])  # write X coordinate (raw_data)
                    x_coordinates.append(core_result[0]['x'])  # save X coordinate for heatmap
                    current_row.write(2, core_result[0]['y'])  # write Y coordinate
                    snr_sheet.row(result_start_row).write(raw_data_col + 2,
                                                          core_result[0]['y'])  # write Y coordinate (raw data)
                    y_coordinates.append(core_result[0]['y'])  # save Y coordinate for heatmap

                    points.append(
                        "(" + str(round(core_result[0][0], 1)) + ", " + str(round(core_result[0][1], 1)) + ")")
                    if core_result[1] < core_pf:
                        current_row.write(3, core_result[1], style=self.fail_style)  # write SNR value to XL
                    else:
                        current_row.write(3, core_result[1])  # write SNR value to XL
                    core_snr_values.append(core_result[1])
                    current_core_snr_values.append(core_result[1])
                    all_snr_values.append(core_result[1])  # get SNR values of core
                    current_row_num += 1

                    result_iteration = 0
                    # write our X and Y nodes
                    for nodes in core_result[2][0]:
                        # write x and Y nodes for raw data
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 3,
                                                                                 nodes[0])  # write X node
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 4,
                                                                                 nodes[1])  # write Y node
                        result_iteration += 1

                    result_iteration = 0
                    # write out signal and noises
                    for signal in core_result[2][1]:
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 5,
                                                                                 signal)  # write signal
                        result_iteration += 1

                    result_iteration = 0
                    # write out the noise
                    for noise in core_result[2][2]:
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 6,
                                                                                 noise)  # write signal
                        result_iteration += 1

                    result_start_row += 1 + result_iteration

                raw_data_col += 8

                snr_sheet.row(current_row_num).write(1, part_name + " EDGE:", style=self.bold_style)
                current_row_num += 1

                # write edge raw data
                snr_sheet.col(raw_data_col).width = 256 * 20
                snr_sheet.row(raw_data_start_row).write(raw_data_col, part_name + " Edge:",
                                                        style=self.bold_style)
                snr_sheet.row(raw_data_start_row + 1).write(raw_data_col, "Iteration " + str(test_iteration + 1) + ":",
                                                            style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 1, "X", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 2, "Y", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 3, "X_NODE", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 4, "Y_NODE", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 5, "SIGNAL", style=self.bold_style)
                snr_sheet.row(raw_data_start_row).write(raw_data_col + 6, "NOISE", style=self.bold_style)

                # iterate over all the edge results
                result_start_row = 1 + raw_data_start_row  # reset the starting row to be in line with the core
                for edge_result in snr_result[1][test_iteration]:
                    current_row = snr_sheet.row(current_row_num)  # initialize new row
                    current_row.write(1, edge_result[0]['x'])  # write X coordinate
                    snr_sheet.row(result_start_row).write(raw_data_col + 1, edge_result[0]['x'])  # write X to raw data
                    x_coordinates.append(edge_result[0]['x'])  # save X coordinate for heatmap
                    current_row.write(2, edge_result[0]['y'])  # write Y coordinate
                    snr_sheet.row(result_start_row).write(raw_data_col + 2, edge_result[0]['y'])  # write Y to raw data
                    y_coordinates.append(edge_result[0]['y'])  # save Y coordinate for heatmap
                    points.append(
                        "(" + str(round(edge_result[0][0], 1)) + ", " + str(round(edge_result[0][1], 1)) + ")")

                    if edge_result[1] < edge_pf:
                        current_row.write(3, edge_result[1], style=self.fail_style)  # write SNR value to XL
                    else:
                        current_row.write(3, edge_result[1])  # write SNR value to XL
                    edge_snr_values.append(edge_result[1])
                    current_edge_snr_values.append(edge_result[1])
                    all_snr_values.append(edge_result[1])
                    current_row_num += 1

                    result_iteration = 0
                    # write our X and Y nodes
                    for nodes in edge_result[2][0]:
                        # write x and Y nodes for raw data
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 3,
                                                                                 nodes[0])  # write X node
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 4,
                                                                                 nodes[1])  # write Y node
                        result_iteration += 1

                    result_iteration = 0
                    # write out signal and noises
                    for signal in edge_result[2][1]:
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 5,
                                                                                 signal)  # write signal
                        result_iteration += 1

                    result_iteration = 0
                    # write out the noise
                    for noise in edge_result[2][2]:
                        snr_sheet.row(result_start_row + result_iteration).write(raw_data_col + 6,
                                                                                 noise)  # write signal
                        result_iteration += 1

                    result_start_row += 1 + result_iteration

                current_row_num += 1
                raw_data_col += 8

                # print a table for the specific test
                self.snr_print_table(current_test_start_row, 29, core_pf, edge_pf, current_core_snr_values,
                                     current_edge_snr_values, snr_sheet, part_name=part_name,
                                     test_iteration=test_iteration + 1)

                plt.bar(points, all_snr_values)
                plt.title("SNR results for " + part_name + ", iteration " + str(test_iteration + 1))
                plt.xticks(rotation=30)
                plt.xticks(fontsize=6)
                plt.savefig("snr_results_graph.png")
                plt.close()
                img = Image.open("snr_results_graph.png")
                r, g, b, a = img.split()
                img = Image.merge("RGB", (r, g, b))
                img.save('snr_graph_for_excel.bmp')
                row_num_for_image = int(2 + 30 * test_iteration + 30 * len(snr_result[0] * screen_iteration))
                snr_sheet.insert_bitmap('snr_graph_for_excel.bmp', row_num_for_image, 5)
                os.remove('snr_graph_for_excel.bmp')
                os.remove("snr_results_graph.png")
                current_row_num = 2 + 30 * (test_iteration + 1) + (30 * len(snr_result[0] * screen_iteration))

                x_ls = list()
                y_ls = list()
                z_ls = list()
                copy_ls = list()

                # iterate over data points and figure the SNRS for the heatmap
                for point_data in snr_result[0][test_iteration]:  # iterate over core data
                    nodes = point_data[2][0]
                    signals = point_data[2][1]
                    noises = point_data[2][2]
                    snrs = list()
                    for i in range(len(signals)):
                        if noises[i] != 0:
                            snrs.append(signals[i] / noises[i])
                        else:
                            snrs.append(0)
                    for node, snr in zip(nodes, snrs):
                        if node not in copy_ls:
                            x_ls.append(node[0])  # append x node
                            y_ls.append(node[1])  # append y node
                            copy_ls.append(node)  # add node to copy list
                            z_ls.append(snr)

                for point_data in snr_result[1][test_iteration]:  # iterate over edge
                    nodes = point_data[2][0]
                    signals = point_data[2][1]
                    noises = point_data[2][2]
                    snrs = list()
                    for i in range(len(signals)):
                        if noises[i] != 0:
                            snrs.append(signals[i] / noises[i])
                        else:
                            snrs.append(0)
                    for node, snr in zip(nodes, snrs):
                        if node not in copy_ls:
                            x_ls.append(node[0])  # append x node
                            y_ls.append(node[1])  # append y node
                            copy_ls.append(node)  # add node to copy list
                            z_ls.append(snr)

                x_arr = np.array(x_ls)
                y_arr = np.array(y_ls)
                z_arr = np.array(z_ls)
                df = pd.DataFrame.from_dict(np.array([x_arr, y_arr, z_arr]).T)
                df.columns = ['X_value', 'Y_value', 'Z_value']
                df['Z_value'] = pd.to_numeric(df['Z_value'])
                pivotted = df.pivot('Y_value', 'X_value', 'Z_value')
                sns.heatmap(pivotted, cmap='magma')
                plt.title("Heatmap for " + part_name + ", iteration " + str(test_iteration + 1))
                plt.savefig("snr_heatmap.png")
                plt.close()

                img = Image.open("snr_heatmap.png")
                r, g, b, a = img.split()
                img = Image.merge("RGB", (r, g, b))
                img.save('snr_heatmap_for_excel.bmp')
                snr_sheet.insert_bitmap('snr_heatmap_for_excel.bmp', row_num_for_image, 17)
                os.remove("snr_heatmap_for_excel.bmp")
                os.remove("snr_heatmap.png")

                test_iteration += 1
            screen_iteration += 1

        final_table_col = 38

        self.snr_print_table(3, final_table_col, core_pf, edge_pf, core_snr_values, edge_snr_values, snr_sheet)

    def save_lin(self, book: xlwt.Workbook, linearity_results, core_pf, edge_pf, function) -> None:
        """
        Saves linearity data to an Excel workbook

        :param book: xlwt book to save to
        :param linearity_results: results of the linearity test
        :param edge_pf: pass/fail condition of the edge
        :param core_pf: pass/fail condition of the core

        :param function: Special parameter --> this parameter is a reference to a function, specifically the
                                               robot controller's convert_robot_to_screen_coordinates

        :return: N/A
        """
        # set up layout for Linearity
        lin_sheet = book.add_sheet("Linearity Results")

        # set column widths to be bigger if they need to be
        lin_sheet.col(11).width = 256 * 20
        lin_sheet.col(12).width = 256 * 13
        lin_sheet.col(21).width = 256 * 13

        row = 1
        iterations = 0

        raw_col = 30
        current_table_row_core = 0
        current_table_row_edge = 0

        all_edge_distances = list()
        all_core_distances = list()

        for linearity_result in linearity_results:
            part_name = linearity_result[-1]

            for i in range(1, len(linearity_result[1]) + 1):
                bmp = "lin_graph_for_excel_part_" + part_name + str(i) + ".bmp"
                lin_sheet.insert_bitmap(bmp, row, 1)
                os.remove(bmp)
                row += 30

            core_distances = list()

            start_col = 12
            count = 1
            for test_iter in linearity_result[0]:
                param_row = lin_sheet.row(2 + current_table_row_core)
                core_row = lin_sheet.row(4 + current_table_row_core)
                current_table_row_core += 30
                # fixme make sure this works
                param_row.write(start_col - 1, part_name + ", Iteration " + str(count), style=self.bold_style)
                param_row.write(start_col, "Parameter", style=self.bold_style)
                param_row.write(start_col + 1, "Min", style=self.bold_style)
                param_row.write(start_col + 2, "Average", style=self.bold_style)
                param_row.write(start_col + 3, "Max", style=self.bold_style)
                param_row.write(start_col + 4, "Units", style=self.bold_style)
                param_row.write(start_col + 5, "Expected", style=self.bold_style)
                param_row.write(start_col + 6, "Units", style=self.bold_style)

                # Core Linearity layer
                #core_row.write(start_col, "Linearity Core")
                #core_row.write(start_col + 1, min(test_iter))
                #core_row.write(start_col + 2, sum(test_iter) / len(test_iter))
                #core_row.write(start_col + 3, max(test_iter))
                #core_row.write(start_col + 4, "mm")
                #core_row.write(start_col + 5, core_pf)
                #core_row.write(start_col + 6, "mm")
                #count += 1

                for distance in test_iter:
                    core_distances.append(distance)
                    all_core_distances.append(distance)

            edge_distances = list()

            for test_iter in linearity_result[1]:
                edge_row = lin_sheet.row(3 + current_table_row_edge)
                current_table_row_edge += 30
                # Edge Linearity layer
                edge_row.write(start_col, "Linearity edge")
                edge_row.write(start_col + 1, min(test_iter))
                edge_row.write(start_col + 2, sum(test_iter) / len(test_iter))
                edge_row.write(start_col + 3, max(test_iter))
                edge_row.write(start_col + 4, "mm")
                edge_row.write(start_col + 5, edge_pf)
                edge_row.write(start_col + 6, "mm")
                for distance in test_iter:
                    edge_distances.append(distance)
                    all_edge_distances.append(distance)

            test_num = 1
            for test_iter in linearity_result[2]:
                # write line start/end
                current_row = lin_sheet.row(2)
                current_row.write(raw_col + 1, "Linearity Test for part: " + part_name + " " + str(test_num),
                                  style=self.bold_style)
                test_num += 1
                current_row = lin_sheet.row(4)
                current_row.write(raw_col, "Line Start", style=self.bold_style)
                current_row = lin_sheet.row(5)
                current_row.write(raw_col, "Line End", style=self.bold_style)
                raw_col += 1
                # iterate over all tests
                for test in test_iter:
                    row_counter = 3
                    current_row = lin_sheet.row(row_counter)
                    row_counter += 1
                    current_row.write(raw_col, "X", style=self.bold_style)
                    current_row.write(raw_col + 1, "Y", style=self.bold_style)
                    current_row = lin_sheet.row(row_counter)
                    row_counter += 1
                    start = test[0].get_start_point()
                    # start = self.convert_robot_to_screen_coordinates(start['x'], start['y'])
                    start = function(start['x'], start['y'])
                    end = test[0].get_end_point()
                    # end = self.convert_robot_to_screen_coordinates(end['x'], end['y'])
                    end = function(end['x'], end['y'])
                    current_row.write(raw_col, start['x'])
                    current_row.write(raw_col + 1, start['y'])
                    current_row = lin_sheet.row(row_counter)
                    row_counter += 1
                    current_row.write(raw_col, end['x'])
                    current_row.write(raw_col + 1, end['y'])
                    # print guessed points to excel
                    for i in range(len(test) - 1):
                        current_row = lin_sheet.row(row_counter)
                        row_counter += 1
                        pt = test[i + 1]
                        current_row.write(raw_col, pt['x'])
                        current_row.write(raw_col + 1, pt['y'])
                    raw_col += 3
                start_col += 1
                raw_col += 1
            iterations += 1

        lin_labels_row = lin_sheet.row(2)
        lin_full_row = lin_sheet.row(3)
        lin_core_row = lin_sheet.row(4)
        final_table_start_col = 21

        lin_labels_row.write(final_table_start_col - 1, "Overall:", style=self.bold_style)
        lin_labels_row.write(final_table_start_col, "Parameter", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 1, "Min", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 2, "Average", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 3, "Max", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 4, "Units", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 5, "Expected", style=self.bold_style)
        lin_labels_row.write(final_table_start_col + 6, "Units", style=self.bold_style)

        # Edge Linearity layer
        lin_full_row.write(final_table_start_col, "Linearity Full")
        lin_full_row.write(final_table_start_col + 1, min(all_edge_distances))
        lin_full_row.write(final_table_start_col + 2, sum(all_edge_distances) / len(all_edge_distances))
        lin_full_row.write(final_table_start_col + 3, max(all_edge_distances))
        lin_full_row.write(final_table_start_col + 4, "mm")
        lin_full_row.write(final_table_start_col + 5, edge_pf)
        lin_full_row.write(final_table_start_col + 6, "mm")

        # Core Linearity layer
        #lin_core_row.write(final_table_start_col, "Linearity Core")
        #lin_core_row.write(final_table_start_col + 1, min(all_core_distances))
        #lin_core_row.write(final_table_start_col + 2, sum(all_core_distances) / len(all_core_distances))
        #lin_core_row.write(final_table_start_col + 3, max(all_core_distances))
        #lin_core_row.write(final_table_start_col + 4, "mm")
        #lin_core_row.write(final_table_start_col + 5, core_pf)
        #lin_core_row.write(final_table_start_col + 6, "mm")

        os.remove("lin_image.png")

    def save_final_sheet(self, book: xlwt.Workbook, acc_params: list, snr_params: list, jit_params: list,
                         lin_params: list, sensor_data=None):

        if len(acc_params) != 7 or len(snr_params) != 7 or len(jit_params) != 7 or len(lin_params) != 6:
            raise Exception("Invalid data input into save function")

        final_sheet = book.add_sheet("Final Sheet")
        param_desc_col = 1
        param_col = 2
        row_num = 1

        # set column width of description to be bigger
        final_sheet.col(1).width = 256 * 23

        # write ACC parameters
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_col, "Accuracy:", style=self.bold_style)
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "# of touches at each pt:", style=self.bold_style)
        current_row.write(param_col, acc_params[0])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Touch Duration(sec):", style=self.bold_style)
        current_row.write(param_col, acc_params[1])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Sec between touches:", style=self.bold_style)
        current_row.write(param_col, acc_params[2])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Probe Size (mm):", style=self.bold_style)
        current_row.write(param_col, acc_params[3])
        current_row = final_sheet.row(row_num)
        row_num += 2
        current_row.write(param_desc_col, "Test Iterations:", style=self.bold_style)
        current_row.write(param_col, acc_params[4])

        # write SNR parameters
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_col, "SNR:", style=self.bold_style)
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "# of noise samples:", style=self.bold_style)
        current_row.write(param_col, snr_params[0])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "# of signal samples:", style=self.bold_style)
        current_row.write(param_col, snr_params[1])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Sec between touches:", style=self.bold_style)
        current_row.write(param_col, snr_params[2])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Probe size (mm):", style=self.bold_style)
        current_row.write(param_col, snr_params[3])
        current_row = final_sheet.row(row_num)
        row_num += 2
        current_row.write(param_desc_col, "Test Iterations:", style=self.bold_style)
        current_row.write(param_col, snr_params[4])

        # write JIT parameters
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_col, "JITTER:", style=self.bold_style)
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "# of touches at each pt:", style=self.bold_style)
        current_row.write(param_col, jit_params[0])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Touch Duration:", style=self.bold_style)
        current_row.write(param_col, jit_params[1])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Sec between touches:", style=self.bold_style)
        current_row.write(param_col, jit_params[2])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Probe Size (mm):", style=self.bold_style)
        current_row.write(param_col, jit_params[3])
        current_row = final_sheet.row(row_num)
        row_num += 2
        current_row.write(param_desc_col, "Test Iterations:", style=self.bold_style)
        current_row.write(param_col, jit_params[4])

        # write LIN parameters
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_col, "LINEARITY:", style=self.bold_style)
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Path Velocity:", style=self.bold_style)
        current_row.write(param_col, lin_params[0])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Sec between touches:", style=self.bold_style)
        current_row.write(param_col, lin_params[1])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Probe Size (mm):", style=self.bold_style)
        current_row.write(param_col, lin_params[2])
        current_row = final_sheet.row(row_num)
        row_num += 1
        current_row.write(param_desc_col, "Test Iterations:", style=self.bold_style)
        current_row.write(param_col, lin_params[3])

        if sensor_data and len(sensor_data) == 3:
            uut_desc_col = 4
            final_sheet.col(uut_desc_col).width = 256 * 21  # 1 unit in xlwt is 256, so this will have a width of 14
            uut_col = 5
            row_num = 1
            final_sheet.row(row_num).write(uut_desc_col, "UUT Information:", style=self.bold_style)
            row_num += 1
            final_sheet.row(row_num).write(uut_desc_col, "Sensor Type:", style=self.bold_style)
            final_sheet.row(row_num).write(uut_col, sensor_data[0])
            row_num += 1
            final_sheet.row(row_num).write(uut_desc_col, "Sensor Configuration:", style=self.bold_style)
            final_sheet.row(row_num).write(uut_col, sensor_data[1])
            row_num += 1
            final_sheet.row(row_num).write(uut_desc_col, "Touch Controller:", style=self.bold_style)
            final_sheet.row(row_num).write(uut_col, sensor_data[2])

    def snr_print_table(self, start_row: int, start_col: int, core_pf: float, edge_pf: float,
                        core_snr_values: list, edge_snr_values: list, snr_sheet: xlwt.Worksheet, part_name=None,
                        test_iteration=None):
        """
        creates a table on an excel worksheet with SNR data
        start row/col reference the top left of the table
        :param start_row: row to start table at
        :param start_col: column to start the table at
        :param core_pf: pass/fail condition of the core
        :param edge_pf: pass/fail condition of the edge
        :param core_snr_values: snr values of the core
        :param edge_snr_values: snr values of the edge
        :param snr_sheet: snr sheet to write one
        :param part_name: name of the part
        :param test_iteration: iteration of the test for the given part
        :return: N/A
        """
        if part_name and test_iteration:
            snr_sheet.row(start_row).write(start_col, part_name + ", iteration " + str(test_iteration),
                                           style=self.bold_style)
        else:
            snr_sheet.row(start_row).write(start_col, "Overall:", style=self.bold_style)

        # top layer outline
        snr_sheet.row(start_row + 1).write(start_col, "Parameter", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 1, "Min", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 2, "Average", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 3, "Max", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 4, "Units", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 5, "Expected", style=self.bold_style)
        snr_sheet.row(start_row + 1).write(start_col + 6, "Units", style=self.bold_style)

        # SNR edge layer
        snr_sheet.row(start_row + 2).write(start_col, "SNR Edge", style=self.bold_style)
        snr_sheet.row(start_row + 2).write(start_col + 1, min(edge_snr_values))
        snr_sheet.row(start_row + 2).write(start_col + 2, sum(edge_snr_values) / len(edge_snr_values))
        snr_sheet.row(start_row + 2).write(start_col + 3, max(edge_snr_values))
        snr_sheet.row(start_row + 2).write(start_col + 4, "mm")
        snr_sheet.row(start_row + 2).write(start_col + 5, edge_pf)
        snr_sheet.row(start_row + 2).write(start_col + 6, "mm")

        # SNR core layer
        snr_sheet.row(start_row + 3).write(start_col, "SNR Core", style=self.bold_style)
        snr_sheet.row(start_row + 3).write(start_col + 1, min(core_snr_values))
        snr_sheet.row(start_row + 3).write(start_col + 2, sum(core_snr_values) / len(core_snr_values))
        snr_sheet.row(start_row + 3).write(start_col + 3, max(core_snr_values))
        snr_sheet.row(start_row + 3).write(start_col + 4, "mm")
        snr_sheet.row(start_row + 3).write(start_col + 5, core_pf)
        snr_sheet.row(start_row + 3).write(start_col + 6, "mm")

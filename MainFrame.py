###########################################
#                                         #
# Touchscreen Testing Verification        #
# Author: Mitchell Allen                  #
# Date: 6/1/2021                          #
# Revision: 1                             #
#                                         #
###########################################

# pubsub is used like an observer pattern: to get a listener to get
# data from one Frame to another one
import struct

import wx
from pubsub import pub
from wx import *

from DXFReader import *
from RobotController import RobotController
from TestManager import TestManager
from TouchController import *

import xlrd
import pdb

WINDOW_WIDTH = 650
WINDOW_HEIGHT = 400

SCALES = [".5 mm", "1 mm", "3 mm", "5 mm", "10 mm", "25 mm", "50 mm"]


def is_valid_filename(filename: str):
    """
    determines if a filename is valid or not
    :param filename: name of the file
    :return: bool representing if the filename is valid
    """
    if filename == "":
        return False
    invalid_words = ["AUX", "CLOCK$", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "CON",
                     "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9", "NUL", "PRN"]
    invalid_chars = [hex(i) for i in range(32)]
    invalid_chars.extend(['"', '*', '/', ':', '<', '>', '?', '\\', '|', '%', 0x7F])
    if filename in invalid_words:
        return False
    for char in filename:
        if char in invalid_chars:
            return False
    return True


class MainFrame(Frame):

    def __init__(self, parent: Window, name: str):
        """
        Main GUI component of the program.
        :param parent: parent of the window
        :param name: name of the window
        """
        Frame.__init__(self, parent, title=name, size=(WINDOW_WIDTH, WINDOW_HEIGHT))
        self.Center()  # center window on screen

        # initialize variables for seeing if data is uploaded
        self._dxf_is_uploaded = False
        self._config_is_uploaded = False

        # initialize Variables that start as none
        self._movement_increment = 10
        self._dxf_reader = None
        self._tests_to_run = []
        self._test_parameters = []  # 1:ACC  2:SNR  3:JIT  4:LIN
        self._offsets = None
        self._screen_dimensions = None

        self._panel = Panel(self)
        self.CreateStatusBar()  # A statusBar in the bottom of the window
        self._panel.SetBackgroundColour('#EBE2E1')  # set default color background to be white-ish
        self.SetMinSize(self.GetSize())  # set minimum size of window to be initialization size

        # set up UUT textFields
        self._uut_tb1, self._uut_tb2 = self.uut_setup()

        # nasty way of getting controls PART 2: MOVEMENT SETUP
        self._z_inc_button, self._home_button = self.position_buttons_setup()

        # set up Z setting button
        self._z_setter_button = Button(self._panel, id=-1, label="Set\nZ\nPoint",
                                       size=(self._z_inc_button.Size[0] * 3.5,
                                             self._z_inc_button.Size[1] * 2),
                                       pos=(self._z_inc_button.Position[0] + self._z_inc_button.Size[0],
                                            self._z_inc_button.Position[1]))
        self._z_setter_button.Bind(EVT_BUTTON, self.on_z_set)

        # Set up coordinate setter controls
        self._x_ctrl, self._y_ctrl, self._z_ctrl, self._coord_setter = self.coord_setter_setup()

        self._dxf_upload, self._xls_button = self.config_setup()

        self._run_toggle, self._checkboxes, self._3x3_rb, self._5x5_rb = self.run_and_checkbox_setup()  # Set up TOGGLE RUN

        self._dxf_text = StaticText(self._panel, id=-1, label='DXF File: ',
                                    size=self._checkboxes[0].Size,
                                    pos=(self._checkboxes[3].Position[0], self._checkboxes[3].Position[1] + 20))

        self._xls_text = StaticText(self._panel, id=-1, label='XLS File: ',
                                    size=self._checkboxes[0].Size,
                                    pos=(self._dxf_text.Position[0], self._dxf_text.Position[1] + 20))

        self._com_port_text = StaticText(self._panel, id=-1, label='COM Port: ',
                                         size=self._checkboxes[0].Size,
                                         pos=(self._xls_text.Position[0], self._xls_text.Position[1] + 20))

        # set window Icon to a logo
        icon = Icon()
        icon.CopyFromBitmap(wx.Bitmap("xymox_icon_real.png", wx.BITMAP_TYPE_ANY))
        self.SetIcon(icon)

        self.menu_bar_setup()  # set up menu bar
        self.Show(True)  # show the frame

        device_connected = False
        try:
            self._robot_controller = RobotController()  # create new robot controller
            self.test_manager = TestManager(self._robot_controller)
            # subscribe to pubsub titles
            pub.subscribe(self.on_parameter_pubsub, "completed_params")  # for uploading xls data
            pub.subscribe(self.on_successful_config, "can_check_config")
            self._com_port_text.SetLabel("COM Port: " + self._robot_controller.get_current_com_port())
            device_connected = True
        except usb.USBError:
            dlg = MessageDialog(self, "There was an issue connecting with the TouchController\n\n USB error occurred.",
                                "Touch Controller Connection Issue")
            dlg.ShowModal()
            dlg.Destroy()
        except ZeroIndexInvalid:
            dlg = MessageDialog(self, "Device Returned error code when clearing buffer.\n\nRun the MXT-APP, "
                                      "once it has been ran quit out and it should resolve this issue.",
                                "Touch Controller Requires Resetting.")
            dlg.ShowModal()
            dlg.Destroy()
        except errors.NoDeviceError:
            dlg = MessageDialog(self, "No Connection Established with Touch Controller.\n\nDouble check that is "
                                      "connected and restart the program.",
                                "Touch Controller Not Connected")
            dlg.ShowModal()
            dlg.Destroy()
        except errors.InvalidInput:
            dlg = MessageDialog(self, "Reset bit of program not properly set.\n\nDid you cancel the program "
                                      "part-way through the run? Use MXT-APP to reset the board.",
                                "Unable to reset the board")
            dlg.ShowModal()
            dlg.Destroy()
        except NoInputFromController:
            dlg = MessageDialog(self, "Touch Controller did not send any messages to be read.\n\nIt is recommended "
                                      "that you check to make sure that the connections are correct and that the "
                                      "board is properly configured.",
                                "No Input From Controller")
            dlg.ShowModal()
            dlg.Destroy()
        if not device_connected:
            self.Destroy()
        else:
            dc = ClientDC(self._panel)
            dc.DrawBitmap(Bitmap("xymox_logo_resized.png"),
                          self._coord_setter.Position[0],
                          self._coord_setter.Position[1] + 60)

    #######################
    # BEGIN SETUP METHODS #
    #######################

    def config_setup(self):
        """
        sets up the configuration buttons on the top right of the screen
        :return: dxf config button, xls config button
        """
        config_label = StaticText(self._panel, label="Config Upload:",
                                  pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT / 50))
        dxf_font = Font(16, wx.DECORATIVE, wx.BOLD, wx.NORMAL)
        config_label.SetFont(dxf_font)

        dxf_button = Button(self._panel, id=-1, size=(120, 30), label="Upload DXF File",
                               pos=(config_label.Position[0], config_label.Position[1] + 30))
        dxf_button.Bind(EVT_BUTTON, self.on_upload_dxf)

        xls_button = Button(self._panel, id=-1, size=(120, 30), label="Upload Config",
                            pos=(dxf_button.Position[0], dxf_button.Position[1] + 35))
        xls_button.Bind(EVT_BUTTON, self.on_select_parameters)
        return dxf_button, xls_button

    def coord_setter_setup(self, textbox_width=30, textbox_height=20):
        """
        sets up the coordinate setter GUI components
        :param textbox_width: desired width of the textbox
        :param textbox_height: desired height of the textbox
        :return: x button, y button, z button, and the coordinate setter
        """
        x_ctrl = TextCtrl(self._panel, id=-1, size=(textbox_width, textbox_height),
                          pos=(self._home_button.Position[0], self._home_button.Position[1] + 40))
        y_ctrl = TextCtrl(self._panel, id=-1, size=(textbox_width, textbox_height),
                          pos=(self._home_button.Position[0] + textbox_width, self._home_button.Position[1] + 40))
        z_ctrl = TextCtrl(self._panel, id=-1, size=(textbox_width, textbox_height),
                          pos=(self._home_button.Position[0] + 2 * textbox_width, self._home_button.Position[1] + 40))

        coord_setter = Button(self._panel, id=-1, label="Set Coordinates",
                              size=(3 * textbox_width + 2, textbox_height + 5),
                              pos=(self._home_button.Position[0], self._home_button.Position[1] + 60))
        coord_setter.Bind(EVT_BUTTON, self.on_set_coordinates)

        return x_ctrl, y_ctrl, z_ctrl, coord_setter

    def menu_bar_setup(self):
        """
        Sets up menubar for the maine frame of the program

        NOTE: when binding methods, adding the method that is called on the event
        with a parenthesis () has the method get called once, if no parenthesis
        then the method is only called when the event occurs
        """
        # set up file menu
        general_menu = Menu()
        menu_about = general_menu.Append(ID_ABOUT, "&About", " Information about this program")
        self.Bind(EVT_MENU, self.on_about, menu_about)
        general_menu.AppendSeparator()
        menu_troubleshooting = general_menu.Append(ID_HELP, "&Troubleshooting", "Display help dialogue")
        self.Bind(EVT_MENU, self.on_help, menu_troubleshooting)
        general_menu.AppendSeparator()
        menu_exit = general_menu.Append(ID_EXIT, "E&xit", " Terminate the program")
        self.Bind(EVT_MENU, self.on_exit, menu_exit)  # bind exit selection to onExit method

        # set up Robot menu
        robot_menu = Menu()
        menu_change_com = robot_menu.Append(ID_NETWORK, "&Change COM port connection",
                                            "Change port to send directions to robot from")
        self.Bind(EVT_MENU, self.on_change_port, menu_change_com)
        robot_menu.AppendSeparator()
        menu_parameters = robot_menu.Append(ID_PROPERTIES, "&Parameters for test", " Select parameters for tests")
        self.Bind(EVT_MENU, self.on_select_parameters, menu_parameters)

        # set up hardware menu
        hardware_menu = Menu()
        menu_change_robot = hardware_menu.Append(ID_FILE8, "Select XYZ &Robot",
                                                 "Select XYZ robot being used to move the finger")
        self.Bind(EVT_MENU, self.on_change_robot, menu_change_robot)
        hardware_menu.AppendSeparator()
        menu_change_touch_controller = hardware_menu.Append(ID_FILE9, "Select &TouchController",
                                                            "Select TouchController to read in data from the touch"
                                                            " screen.")
        self.Bind(EVT_MENU, self.on_change_touch_controller, menu_change_touch_controller)

        # prepare menuBar to be added to frame
        menubar = MenuBar()
        menubar.Append(general_menu, "&General")  # add general_menu to MenuBar
        menubar.Append(robot_menu, "&Robot Actions")  # add test_menu to MenuBar
        menubar.Append(hardware_menu, "Hardware &Selection")
        self.SetMenuBar(menubar)

    def position_buttons_setup(self, button_width=30, button_height=30):
        """
        sets up the buttons to manually control the robot in the top left of the GUI
        :param button_width: desired width of the buttons
        :param button_height: desired height of the buttons
        :return: z button, home button
        """
        height_div = 12

        x_inc_button = Button(self._panel, id=-1, label="+",
                              pos=(WINDOW_WIDTH / 50, WINDOW_HEIGHT / height_div),
                              size=(button_width, button_height), name="x inc")
        x_inc_button.Bind(EVT_BUTTON, self.on_move_robot)

        x_dec_button = Button(self._panel, id=-1, label="-",
                              pos=(WINDOW_WIDTH / 50, WINDOW_HEIGHT / height_div + button_height),
                              size=(button_width, button_height), name="x dec")
        x_dec_button.Bind(EVT_BUTTON, self.on_move_robot)

        y_inc_button = Button(self._panel, id=-1, label="+",
                              pos=(WINDOW_WIDTH / 50 + button_width, WINDOW_HEIGHT / height_div),
                              size=(button_width, button_height), name="y inc")
        y_inc_button.Bind(EVT_BUTTON, self.on_move_robot)

        y_dec_button = Button(self._panel, id=-1, label="-",
                              pos=(WINDOW_WIDTH / 50 + button_width, WINDOW_HEIGHT / height_div + button_height),
                              size=(button_width, button_height), name="y dec")
        y_dec_button.Bind(EVT_BUTTON, self.on_move_robot)

        z_inc_button = Button(self._panel, id=-1, label="+",
                              pos=(WINDOW_WIDTH / 50 + button_width * 2, WINDOW_HEIGHT / height_div),
                              size=(button_width, button_height), name="z inc")
        z_inc_button.Bind(EVT_BUTTON, self.on_move_robot)

        z_dec_button = Button(self._panel, id=-1, label="-",
                              pos=(WINDOW_WIDTH / 50 + button_width * 2, WINDOW_HEIGHT / height_div + button_height),
                              size=(button_width, button_height), name="z dec")
        z_dec_button.Bind(EVT_BUTTON, self.on_move_robot)

        label_font = Font(14, wx.DECORATIVE, wx.BOLD, wx.NORMAL)
        movement_x = StaticText(self._panel, label="X",
                                pos=(
                                    WINDOW_WIDTH / 50 + button_width / 3,
                                    WINDOW_HEIGHT / height_div - button_height / 1.5 - 5))
        movement_x.SetFont(label_font)

        movement_y = StaticText(self._panel, label="Y",
                                pos=(
                                    WINDOW_WIDTH / 50 + 1.25 * button_width,
                                    WINDOW_HEIGHT / height_div - button_height / 1.5 - 5))
        movement_y.SetFont(label_font)

        movement_z = StaticText(self._panel, label="Z",
                                pos=(
                                    WINDOW_WIDTH / 50 + 2.25 * button_width,
                                    WINDOW_HEIGHT / height_div - button_height / 1.5 - 5))
        movement_z.SetFont(label_font)

        scale_box = Choice(self._panel, id=-1, size=(3 * button_width, button_height),
                           pos=(WINDOW_WIDTH / 50, WINDOW_HEIGHT / height_div + 2 * button_height + 5),
                           choices=SCALES)
        scale_box.SetSelection(4)
        scale_box.Bind(EVT_CHOICE, self.on_change_inc)

        home_button = Button(self._panel, id=-1, label="Move Home", size=(3 * button_width, button_height),
                             pos=(WINDOW_WIDTH / 50, WINDOW_HEIGHT / height_div + 3 * button_height))
        home_button.Bind(EVT_BUTTON, self.on_home)

        return z_inc_button, home_button

    def run_and_checkbox_setup(self, button_width=200, button_height=50):
        """
        creates the run button and the checkboxes below it
        :param button_width: width of run button
        :param button_height: height of run button
        :return: the run button and a list containing the checkboxes
        """
        run_toggle = ToggleButton(self._panel, id=-1, label="Run",
                                  pos=((WINDOW_WIDTH - button_width) / 2, WINDOW_HEIGHT * (1 / 50)))
        run_toggle.SetSize((button_width, button_height))
        run_toggle.Bind(EVT_TOGGLEBUTTON, self.on_run_tests)

        tests = ["Accuracy", "Signal-to-Noise (SNR)", "Jitter", "Linearity"]
        checkbox_ls = list()
        rb_1 = rb_2 = None
        # create checkboxes and append them to list
        for i in range(len(tests)):
            mult_change = 3 if i <= 1 else 4
            cb = CheckBox(self._panel, id=-1, label=tests[i],
                          pos=(run_toggle.Position[0], run_toggle.Position[1] + 20 * (i + mult_change)))
            if i == 1:  # case of SNR where radial buttons need to be added
                x_pos = run_toggle.Position[0]
                y_pos = run_toggle.Position[1] + 20 * (i + 4)
                rb_1 = RadioButton(self._panel, label="3x3", pos=(x_pos + 10, y_pos))
                rb_1.SetValue(True)  # 3x3 is default
                rb_2 = RadioButton(self._panel, label="5x5", pos=(x_pos + 50, y_pos))
            checkbox_ls.append(cb)

        return run_toggle, checkbox_ls, rb_1, rb_2

    def uut_setup(self):
        """
        sets up the UUT controls at the bottom right side of the panel
        :return: the three textboxes used to get information regarding the UUT
        """
        height_offset = 280

        uut_label = StaticText(self._panel, label="UUT Information:",
                               pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT - height_offset))
        uut_font = Font(16, wx.DECORATIVE, wx.BOLD, wx.NORMAL)
        uut_label.SetFont(uut_font)

        StaticText(self._panel, label="Sensor Type:",
                   pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT - height_offset + 25))

        tb1 = TextCtrl(self._panel, -1, size=(160, 20),
                       pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT - height_offset + 45))

        StaticText(self._panel, label="Sensor Configuration",
                   pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT - height_offset + 65))

        tb2 = TextCtrl(self._panel, -1, size=(160, 20),
                       pos=(WINDOW_WIDTH - 200, WINDOW_HEIGHT - height_offset + 85))

        return tb1, tb2

    ##############################
    #  BEGIN EVENT METHODS HERE  #
    ##############################

    def on_about(self, e):
        """
        gives information regarding this program to the user
        :param e: event causing this method to be called
        :return: N/A
        """
        msg = "SETUP: \nIn TEACH mode, go to F2-> Control by RS232 -> Enable.\n" \
              "Then switch the red switch on the FN4300 to RUN, this will allow it" \
              "to run off of the program. \n \n NOTE: if you are having issues, " \
              "try switching COM ports (Robot Actions-> Change COM port connection)" \
              "\n\n\nVersion: 1.2"
        dlg = MessageDialog(self, msg, "About Touchscreen Verification", OK)
        dlg.ShowModal()  # Show it
        dlg.Destroy()  # finally destroy it when finished.

    def on_change_inc(self, e):
        """
        Changes the scale of the movement by the manual XYZ controller (top right of panel)
        Sets the self._movement_increment to what the selection is
        :param e: event causing this method to be called (should be selecting a
                  number value to set increment to)
        :return: N/A
        """
        selection = e.GetEventObject().GetCurrentSelection()
        self._movement_increment = float(SCALES[selection].split(" ")[0])

    def on_change_port(self, e):
        """
        cycles the port for connecting to the fisnar 4000.
        :param e:  event causing this method to be called
        :return: N/A
        """
        com_ports = self._robot_controller.get_valid_ports()
        scd = SingleChoiceDialog(parent=self, message="Select COM port to send data to the XYZ robot:",
                                 caption="Select COM port", choices=com_ports)
        scd.ShowModal()
        port = self._robot_controller.set_com_port(scd.GetSelection())  # set the new controller
        self._com_port_text.SetLabel("COM Port: " + port)  # set label text

        dlg = MessageDialog(self, "Now sending information through " + port, "COM port changed", OK)
        dlg.ShowModal()  # Show it
        dlg.Destroy()  # finally destroy it when finished.

    def on_change_robot(self, e):
        """
        Changes the currently selected robot.
        :param e: event causing this method to happen
        :return: N/A
        """
        robots = ["Fisnar F4300N"]  # add robot name to this list if new robot is used
        dlg = SingleChoiceDialog(parent=self, message="Select XYZ Robot", caption="Select Robot:",
                                 choices=robots)
        dlg.ShowModal()
        robot_name = robots[dlg.GetSelection()]
        self._robot_controller.set_robot(robot_name)

    def on_change_touch_controller(self, e):
        """
        sets the touch controller to be what the user selects
        :param e: event causing this method to be called
        :return: None
        """
        controllers = ["Microchip ATMXT1066T2"]  # add touch controller name to this list if new robot is used
        dlg = SingleChoiceDialog(parent=self, message="Select Touch Controller", caption="Select Touch Controller:",
                                 choices=controllers)
        dlg.ShowModal()
        self.test_manager.set_touch_controller(controllers[dlg.GetSelection()])  # set the touch controller

    def on_exit(self, e) -> None:
        """
        close this bad boy
        :param e: event causing this method to be called
        :return: None
        """
        self.Close(True)  # close the program

    def on_help(self, e) -> None:
        """
        lists potential problems and how to fix them
        :param e: event causing this method to be called
        :return: None
        """
        msg = "Known issues to cause the program to not run:\n\n1) Make sure you are sending information to the" \
              " correct COM port. you may need to cycle COM ports a few times to find the correct one.\n\n2) You" \
              " must upload a DXF file and a valid configuration .xls file to run the tests.\n\n3) Make sure the " \
              "touch controller is utilizing the libusb driver, otherwise the program will not be able to read " \
              "information from the device. \n\n4) If the COM port is correct, but the robot is still not registering" \
              " input, take these steps:\n - Turn the robot off\n - Switch the robot to teach mode\n" \
              " - Turn the robot on\n - Go to " \
              "F2 -> Control By RS232 -> enable RS232\n - Switch robot into run mode.\n" \
              "This reset needs to happen sometime whens the robot is not used for a while."
        dlg = MessageDialog(self, msg, "Program Troubleshooting", style=ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def on_home(self, e) -> None:
        """
        communicates with the robot controller to move the arm back to
        it's home position
        :param e: event causing this method to be called
        :return: None
        """
        try:
            self._robot_controller.move_home()
        except TimeoutError:
            dlg = MessageDialog(self, "TimeoutError occurred\n\nMake sure you are connected to the right COM Port.",
                                "Unable to Communicate with the robot.")
            dlg.ShowModal()
            dlg.Destroy()

    def on_move_robot(self, e, debug=False) -> None:
        """
        moves the robot based on the button pressed (top left of window)
        and calls the robot controller to do the work

        This one makes the movements called relative as opposed to absolute, causing it to move
        relative to its current location
        :param e:  event causing this method to be called
        :param debug: bool that determines if debug data is output to console
        :return: nothing
        """
        btn = e.GetEventObject()
        coord = btn.GetName().split(" ")[0]
        lbl = btn.GetLabel()

        signage = 1 if lbl == "+" else -1

        try:
            if coord == "x":
                self._robot_controller.move(signage * self._movement_increment, 0, 0, is_relative=True)
            elif coord == "y":
                self._robot_controller.move(0, signage * self._movement_increment, 0, is_relative=True)
            else:
                self._robot_controller.move(0, 0, signage * self._movement_increment, is_relative=True)
            if debug:
                print(self._robot_controller.get_current_coords())
        except TimeoutError:
            dlg = MessageDialog(self, "Timeout error occurred -- make sure connection is made and the correct COM port"
                                      " is being used",
                                "Timeout Error")
            dlg.ShowModal()
            dlg.Destroy()

    def on_parameter_pubsub(self, msg) -> None:
        """
        handles getting configuration data from the pubsub
        :param msg: list containing an amalgamation of data for the robot
        :return: None
        """
        text = msg.pop(-1)
        if len(text) > 25:
            text = text[:25] + ' ...'
        self._xls_text.SetLabel("XLS File: " + text)
        self.on_z_set(None, value_to_set=msg.pop(-1))  # set z axis
        self._offsets = msg.pop(-1)
        self.test_manager.set_finger_offset(self._offsets)
        self.test_manager.upload_configuration_data(msg)
        self._config_is_uploaded = True

    def on_run_tests(self, e):
        """
        This method runs the tests.

        :param e: event causing this method
        """
        btn = e.GetEventObject()

        at_least_one_test = False
        for cb in self._checkboxes:
            if cb.GetValue():
                at_least_one_test = True

        # check if button is toggled ON
        if btn.GetValue() and at_least_one_test:

            if self._dxf_is_uploaded and self._config_is_uploaded:

                file_dlg = FileDialog(self, "Save Output Data File", style=FD_SAVE,
                                      wildcard=".xls file (*.xls)|*.xls")
                if file_dlg.ShowModal() == ID_OK:

                    # get tests to run
                    tests = list()
                    for cb in self._checkboxes:
                        if cb.GetValue():
                            tests.append(cb.GetLabel())
                    # upload tests to run
                    self.test_manager.upload_tests_to_run(tests)

                    filepath = file_dlg.GetPath()

                    run_failed = is_finished = False
                    is_oriented = self._robot_controller.is_oriented()

                    # run tests until user is done
                    can_save = False
                    while not is_finished:
                        # second while loop to allow user to possibly not cancel
                        cancel = False
                        part_name = ""
                        while not cancel:
                            continue_msg = "Enter identifier for the unit being tested:"
                            continue_title = "Identify part name, cancel to end testing."
                            continue_dlg = TextEntryDialog(self, continue_msg, continue_title, '',
                                                           style=wx.TextEntryDialogStyle | wx.TE_RICH)
                            if continue_dlg.ShowModal() == ID_CANCEL:
                                dlg = MessageDialog(self, "Are you sure you want to finish testing?",
                                                    "Are you sure?", style=YES_NO)
                                is_finished = cancel = dlg.ShowModal() == ID_YES
                            else:
                                part_name = continue_dlg.GetValue()
                                cancel = is_valid_filename(part_name)

                        # while loop finished, see if testing was cancelled
                        if not is_finished:
                            # check if orientation was done or not
                            if not is_oriented:
                                # orient the robot
                                try:
                                    xy_flip, x_flip, y_flip = self.test_manager.orient()
                                    # generate popup message if successful
                                    if xy_flip:
                                        msg1 = "The X & Y axes of the screen are flipped with relation to the X & Y " \
                                               "coordinates of the robot.\n"
                                        if y_flip:
                                            msg2 = "The screen's positive X axis is in the direction of the robot's" \
                                                   " negative Y axis.\n"
                                        else:
                                            msg2 = "The screen's positive X axis is in the direction of the robot's" \
                                                   " positive Y axis.\n"

                                        if x_flip:
                                            msg3 = "The screen's positive Y axis is in the direction of the robot's" \
                                                   " negative X axis.\n"
                                        else:
                                            msg3 = "The screen's positive Y axis is in the direction of the robot's" \
                                                   " positive X axis.\n"
                                    else:
                                        msg1 = "The X & Y axes of the screen are aligned with the axes of the robot.\n"
                                        if x_flip:
                                            msg2 = "The screen's positive X axis is in the direction of the robot's" \
                                                   " negative X axis.\n"
                                        else:
                                            msg2 = "The screen's positive X axis is in the direction of the robot's" \
                                                   " positive X axis.\n"
                                        if y_flip:
                                            msg3 = "The screen's positive Y axis is in the direction of the robot's" \
                                                   " negative Y axis.\n"
                                        else:
                                            msg3 = "The screen's positive Y axis is in the direction of the robot's" \
                                                   " positive Y axis.\n"

                                    dlg = MessageDialog(self, msg1 + msg2 + msg3, "Orientation Successful.")
                                    dlg.ShowModal()
                                    is_oriented = True
                                except TimeoutError:
                                    dlg = MessageDialog(self, "Timeout error occurred. Check to see if the correct COM port is being "
                                                              "used. If that does not work, try restarting the robot.",
                                                        "Cannot communicate with the robot.")
                                    dlg.ShowModal()
                                    run_failed = True
                                except errors.NoInputFromController:
                                    dlg = MessageDialog(self, "Could not read input from the board. The finger either missed the board "
                                                              "or the board failed to return a touch recognition.",
                                                        "Calibration Failed.")
                                    dlg.ShowModal()
                                    run_failed = True
                                except errors.InvalidAxes:
                                    pdb.set_trace()
                                    dlg = MessageDialog(self,
                                                        "Could not calibrate the board properly. Issues occurred when figuring the "
                                                        "positive X and Y axes.",
                                                        "Calibration Failed.")
                                    dlg.ShowModal()
                                    run_failed = True
                                except usb.USBError:
                                    dlg = MessageDialog(self, "USB error occurred, restart the program and ensure the touch controller "
                                                              "is connected to the computer.",
                                                        "Calibration Failed.")
                                    dlg.ShowModal()
                                    run_failed = True
                                except UnicodeDecodeError:
                                    dlg = MessageDialog(self,
                                                        "Error occurred while decoding data from the robot.",
                                                        "Decode Error Encountered")
                                    dlg.ShowModal()
                                    run_failed = True
                            # run the test
                            progress_msg = "These windows may display that they are not responsive, however that " \
                                           "is not the case. The program is running the tests and will update " \
                                           "the progress bar as tests finish."
                            progress_dlg = ProgressDialog("Tests Executing", progress_msg, parent=self,
                                                          style=PD_APP_MODAL | PD_ELAPSED_TIME | PD_REMAINING_TIME)
                            self.test_manager.reset_touch_controller()  # FIXME
                            tests_ran_successfully = False
                            is_import_issue = False
                            if not run_failed:
                                try:
                                    large_read = self._5x5_rb.GetValue() and not self._3x3_rb.GetValue()
                                    tests_ran_successfully = self.test_manager.run_tests(tests, progress_dlg,
                                                                                         part_name=part_name,
                                                                                         is_large_read=large_read)
                                    can_save = True
                                except ImportError:
                                    run_failed = is_import_issue = True
                                if not tests_ran_successfully:
                                    progress_dlg.Destroy()  # Destroy the progress dialog if fail occurs
                                    # show error message to user
                                    if is_import_issue:
                                        err_msg = "Import error occurred, make sure all files are properly formatted."
                                    else:
                                        err_msg = "Error occurred while running the tests, make sure the screen is " \
                                                  "properly configured and that the correct COM port is being utilized."
                                    err_dlg = MessageDialog(self, err_msg, "Tests Failed")
                                    err_dlg.ShowModal()
                            else:
                                progress_dlg.Destroy()
                                is_finished = True

                    if can_save and not run_failed:
                        self.test_manager.save_results(filepath, self._uut_tb1.GetValue(),
                                                                 self._uut_tb2.GetValue())
                        confirm_dlg = MessageDialog(self, "Output saved to: " + filepath, "Save Successful.")
                        confirm_dlg.ShowModal()
            else:
                dlg = MessageDialog(self, "Please upload both a .dxf file and a .xls configuration file.",
                                          "Upload configurations before running tests")
                dlg.ShowModal()

        btn.SetValue(False)  # turn run button off

    def on_select_parameters(self, e):
        """
        Creates a select parameter box.. radical!
        :param e: event causing this to be called
        :return: None
        """
        ParameterWindow(self._panel, "Parameters")

    def on_set_coordinates(self, e):
        """
        Sets the coordinates of the robot
        Moves the robot continuously to the given point (be careful not to break anything!)

        :param e: Event causing this method to be called
        :return: None
        """
        try:
            new_x = float(self._x_ctrl.GetValue())
            new_y = float(self._y_ctrl.GetValue())
            new_z = float(self._z_ctrl.GetValue())
            try:
                self._robot_controller.move(new_x, new_y, new_z)
            except TimeoutError:
                msg = "Timeout error occurred, either the movement took to long or connection was lost/never made."
                dlg = MessageDialog(self, msg, "Timeout Error")
                dlg.ShowModal()
                dlg.Destroy()
        except ValueError:
            dlg = MessageDialog(self, "Coordinates must be number values.", "Invalid Input")
            dlg.ShowModal()
            dlg.Destroy()

    def on_successful_config(self):
        """
        method called when a successful configuration is uploaded
        Draws a pretty little checkmark for the users to stare at for a few seconds
        Super complex, right?

        :return: None
        """
        self.SetStatusText("Configuration Uploaded Successfully")
        dc = ClientDC(self._panel)
        dc.DrawBitmap(Bitmap("checkmark_20x20_t.png"),
                      self._xls_button.Position[0] + self._xls_button.Size[0] + 10,
                      self._xls_button.Position[1] + 5)

    #
    # def on_toggle(self, e):
    #     """
    #     This method runs the tests
    #
    #     :param e: event causing this method
    #     """
    #     btn = e.GetEventObject()
    #     # check if button is toggled ON
    #     if btn.GetValue():
    #         if self._dxf_is_uploaded:
    #             self.SetStatusText("Running Tests")
    #
    #             msg = "These windows may display that they are not responsive, however that is not the case. " \
    #                   "The program is running the tests and will update the progress bar as tests finish."
    #             # initialize progress dialogue for visualizing the progress of the tests
    #             dlg = ProgressDialog("Tests Executing", msg, parent=self,
    #                                  style=PD_APP_MODAL | PD_ELAPSED_TIME | PD_REMAINING_TIME)
    #             tests_ran_successfully = self.test_manager.run_tests(self._tests_to_run, dlg)
    #
    #             if not tests_ran_successfully:
    #                 err_msg = "Unable to communicate with the robot. Double check you are using the correct COM port."
    #                 err_dlg = MessageDialog(self, err_msg, "Tests Failed")
    #                 err_dlg.ShowModal()
    #         else:
    #             dlg = MessageDialog(self, "Please upload an appropriate DXF file before running the test.",
    #                                 "Upload DXF before executing")
    #             dlg.ShowModal()
    #         dlg.Destroy()
    #         btn.SetValue(False)

    def on_upload_dxf(self, e):
        """
        event method called to upload a DXF file
        :param e: event causing this method to occur
        :return: None
        """
        default_directory = ''
        default_name = ''
        dlg = FileDialog(self, 'Upload DXF file',
                         default_directory, default_name, '.dxf files (*.dxf)|*.dxf',
                         FD_OPEN | FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == ID_CANCEL:  # if not saved, end method
            return

        good_import = False

        try:
            if self._offsets:
                self._dxf_reader = DXFReader(dlg.GetPath(), offsets=self._offsets)  # create new DXF reader to be used
            else:
                self._dxf_reader = DXFReader(dlg.GetPath())
            good_import = True
        except errors.BadINSUNITS:
            dlg = MessageDialog(self, "DXF must have $INSUNITS specified.", "File not formatted correctly")
            dlg.ShowModal()
            dlg.Destroy()
        except ImportError:
            dlg = MessageDialog(self, "An import error occurred.", "File not formatted correctly")
            dlg.ShowModal()
            dlg.Destroy()
        if good_import:
            self.test_manager.set_dxf_reader(self._dxf_reader)
            dc = ClientDC(self._panel)
            # draw checkmark indicating a file upload was successful
            dc.DrawBitmap(Bitmap("checkmark_20x20_t.png"),
                          self._dxf_upload.Position[0] + self._dxf_upload.Size[0] + 10,
                          self._dxf_upload.Position[1] + 5)
            self._dxf_is_uploaded = True
            self.SetStatusText(".dxf file uploaded successfully")

            filename = dlg.GetFilename()
            # truncate filename if it's too big for the screen
            if len(filename) > 25:
                filename = filename[:25] + ' ...'
            self._dxf_text.SetLabel("DXF File: " + filename)  # set the label to the filename
            dlg.Destroy()  # Destroy dialog when finished
        else:
            self.SetStatusText(".dxf file upload unsuccessful")

    def on_z_set(self, e, value_to_set=None):
        """
        Sets the Z axis of the robot (for touching the screen)
        :param e: event to cause this method to be called
        :param value_to_set: Default nothing, if you set this then the Z axis is set to whatever this value is
        :return:
        """
        if type(value_to_set) is float:
            z = value_to_set
        else:
            z = self._robot_controller.get_current_z_coord()
        self.test_manager.set_z_start(z)
        dlg = MessageDialog(self, "Z coordinate set to: " + str(z) + " mm.", "Z Coordinate Set")
        dlg.ShowModal()
        dlg.Destroy()

    #################
    # END MAINFRAME #
    #################


class ParameterWindow(Frame):

    def __init__(self, parent: Window, name: str):
        """
        constructor for the ParameterWindow
        Allows the user to upload a .xls file and select other parameters to alter

        :param parent: parent of this window
        :param name: name of this window
        """
        btn_x = 20
        btn_y = 40
        self._btn_w = 100  # button width
        self._btn_h = 40  # button height
        self._width = 3 * btn_x + 2 * self._btn_w
        self._height = 3 * btn_y + 3 * self._btn_h

        self._acc_data = None
        self._lin_data = None
        self._jit_data = None
        self._snr_data = None
        self._finger_data = None
        self._node_data = None
        self._pass_fail_data = None
        self._z_axis = None
        self._xls_filename = None

        Frame.__init__(self, parent, title=name, size=(self._width, self._height))
        self.SetMinSize(self.Size)
        self._main_panel = Panel(self)
        self._main_panel.SetBackgroundColour("#F29E50")
        self.Center()  # center window on screen

        StaticText(self._main_panel, id=-1, label="     Select test to change parameters:", pos=(btn_x, btn_y / 3))

        # Set up controls for users to interact with
        acc_btn = Button(self._main_panel, id=-1, label="Accuracy", pos=(btn_x, btn_y),
                         size=(self._btn_w, self._btn_h))
        acc_btn.Bind(EVT_BUTTON, self.on_acc)

        lin_btn = Button(self._main_panel, id=-1, label="Linearity", pos=(btn_x, acc_btn.Position[1] + self._btn_h),
                         size=(self._btn_w, self._btn_h))
        lin_btn.Bind(EVT_BUTTON, self.on_lin)

        jit_btn = Button(self._main_panel, id=-1, label="Jitter", pos=(btn_x + self._btn_w, btn_y),
                         size=(self._btn_w, self._btn_h))
        jit_btn.Bind(EVT_BUTTON, self.on_jit)

        snr_btn = Button(self._main_panel, id=-1, label="Signal-to-Noise",
                         pos=(btn_x + self._btn_w, jit_btn.Position[1] + self._btn_h),
                         size=(self._btn_w, self._btn_h))
        snr_btn.Bind(EVT_BUTTON, self.on_snr)

        upload_btn = Button(self._main_panel, id=-1, label="Upload Config File",
                            pos=(self._width / 2 - (self._btn_w + 20) / 1.75, snr_btn.Position[1] + self._btn_h),
                            size=(self._btn_w + 20, self._btn_h))
        upload_btn.Bind(EVT_BUTTON, self.on_config)

        self.Bind(EVT_CLOSE, self.on_close)

        # pubsub stuff
        pub.subscribe(self.on_pubsub, "parameter_exchange")
        self.Show(True)

        # set window Icon to a logo
        icon = Icon()
        icon.CopyFromBitmap(wx.Bitmap("xymox_icon_real.png", wx.BITMAP_TYPE_ANY))
        self.SetIcon(icon)

    def on_pubsub(self, msg):
        """
        transfers data to the parent window
        :param msg: message to send, should be a list
        :return: N/A
        """
        test_type = msg[0]
        del msg[0]
        if test_type == "acc":
            self._acc_data = msg
        elif test_type == "lin":
            self._lin_data = msg
        elif test_type == "jit":
            self._jit_data = msg
        elif test_type == "snr":
            self._snr_data = msg
        else:
            raise KeyError("First element of msg does not represent a test to be ran: " + test_type)

        frame = self.GetParent()
        frame.Show()

    def on_acc(self, e):
        """
        Creates a ParamChoose window for the accuracy test.
        :param e: event causing this method to run
        :return: N/A
        """
        params = ["acc", "Number of touches at each point:", "Touch duration:", "Duration between touches:",
                  "Probe size:", "Test iterations:"]
        ParamChoose(self, "Accuracy Parameters", params)

    def on_lin(self, e):
        """
        Creates a ParamChoose window for the linearity test.
        :param e: event causing this method to run
        :return: N/A
        """
        params = ["lin", "Path Velocity:", "Duration between paths:", "Probe Size:", "Test iterations:"]
        ParamChoose(self, "Linearity Parameters", params)

    def on_jit(self, e):
        """
        Creates a ParamChoose window for the jitter test.
        :param e: event causing this method to run
        :return: N/A
        """
        params = ["jit", "Number of touches per point:", "Touch (hold) duration:", "Duration between touches:", "Probe Size:", "Test iterations:"]
        ParamChoose(self, "Jitter Parameters", params)

    def on_snr(self, e):
        """
        Creates a ParamChoose window for the SNR test.
        :param e: event causing this method to run
        :return: N/A
        """
        params = ["snr", "Number of noise samples:", "Number of signal (touch) samples:", "Duration between touches:",
                  "Probe size:", "Test iterations:"]
        ParamChoose(self, "Signal-to-Noise Parameters", params)

    def on_config(self, e):
        """
        Handles when a configuration .xls file is uploaded to the window.
        :param e: event causing this method to run
        :return: N/A
        """
        dlg = FileDialog(self, 'Upload filled .xls template file', '', '',
                         'Template Worksheet (*.xls; *.xlsx)|*.xls; *.xlsx',
                         FD_OPEN | FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == ID_CANCEL:  # if not saved, end method
            return

        if dlg.GetPath()[-3:] != "xls":
            dlg2 = MessageDialog(self._main_panel, "File type must have a .xls extension.",
                                 "Invalid File Extension", style=ICON_ERROR)
            dlg2.ShowModal()
            dlg2.Destroy()
        else:
            self._xls_filename = dlg.GetFilename()
            book = xlrd.open_workbook(dlg.GetPath())
            sheet = book.sheet_by_index(0)
            # initialize data lists
            acc_data = []
            snr_data = []
            jit_data = []
            lin_data = []
            # column to get from = letter of the alphabet-1
            # current template column is C, so col = 3 - 1 = 2
            col = 2
            # boolean for determining if data reading should continue
            # is set false when a bad value is read in, remains true otherwise
            can_upload = True
            # iterate over cells to read in data
            for i in range(0, 5):
                acc_val = sheet.cell_value(rowx=2 + i, colx=col)
                snr_val = sheet.cell_value(rowx=9 + i, colx=col)
                jit_val = sheet.cell_value(rowx=16 + i, colx=col)
                # if statement ignored last
                if not i >= 4:
                    lin_val = sheet.cell_value(rowx=23 + i, colx=col)
                    if self.is_valid(lin_val):
                        lin_data.append(lin_val)
                    else:
                        can_upload = False
                if can_upload and self.is_valid(acc_val) and self.is_valid(snr_val) and self.is_valid(jit_val):
                    acc_data.append(acc_val)
                    snr_data.append(snr_val)
                    jit_data.append(jit_val)
                else:
                    can_upload = False

            if can_upload:
                y_offset = sheet.cell_value(rowx=2, colx=7)
                x_offset = sheet.cell_value(rowx=3, colx=7)
                y_nodes = sheet.cell_value(rowx=6, colx=7)
                x_nodes = sheet.cell_value(rowx=7, colx=7)
                z_axis = sheet.cell_value(rowx=10, colx=7)
                if x_offset == "":
                    y_offset = 0
                if y_offset == "":
                    x_offset = 0
                if x_nodes == "" or y_nodes == "":
                    can_upload = False
                if z_axis == "":
                    z_axis = 0
                finger_data = [x_offset, y_offset]
                node_data = [x_nodes, y_nodes]

                pass_fail_criteria = list()

                acc_edge_pf = sheet.cell_value(rowx=2, colx=4)
                acc_core_pf = sheet.cell_value(rowx=5, colx=4)
                pass_fail_criteria.append((acc_edge_pf, acc_core_pf))

                snr_edge_pf = sheet.cell_value(rowx=9, colx=4)
                snr_core_pf = sheet.cell_value(rowx=12, colx=4)
                pass_fail_criteria.append((snr_edge_pf, snr_core_pf))

                jit_edge_pf = sheet.cell_value(rowx=16, colx=4)
                jit_core_pf = sheet.cell_value(rowx=19, colx=4)
                pass_fail_criteria.append((jit_edge_pf, jit_core_pf))

                lin_edge_pf = sheet.cell_value(rowx=23, colx=4)
                lin_core_pf = sheet.cell_value(rowx=26, colx=4)
                pass_fail_criteria.append((lin_edge_pf, lin_core_pf))

                for edge_core in pass_fail_criteria:
                    for val in edge_core:
                        if val == "":
                            can_upload = False
                if can_upload:
                    # upload data to self
                    self._acc_data = acc_data
                    self._snr_data = snr_data
                    self._jit_data = jit_data
                    self._lin_data = lin_data
                    self._finger_data = finger_data
                    self._node_data = node_data
                    self._pass_fail_data = pass_fail_criteria
                    self._z_axis = z_axis
                    self.on_close(None)
                else:
                    raise ImportError("Pass/Fail criteria or node sizes not specified.")

    def on_close(self, e):
        """
        Closes the window and sends any pertinent data to the MainFrame.
        :param e: event causing this method to run
        :return: N/A
        """

        sorta_valid = self._acc_data is not None and self._jit_data is not None
        data_is_valid = self._snr_data is not None and self._lin_data is not None and sorta_valid

        if data_is_valid:
            data = [self._acc_data, self._snr_data, self._jit_data, self._lin_data,
                    self._pass_fail_data, self._node_data, self._finger_data, self._z_axis, self._xls_filename]
            pub.sendMessage("completed_params", msg=data)
            pub.sendMessage("can_check_config")
        self.Destroy()

    def is_valid(self, val):
        """
        Determines if a value is valid or not.
        :param val: value being evaluated
        :return: N/A
        """
        if val == "":
            dlg = MessageDialog(self._main_panel, "Parameter left blank, unable to upload configuration file. Please "
                                                  "fix parameter and reupload", "Invalid Input", style=ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        # test if value is float
        if type(val) != float:
            dlg = MessageDialog(self._main_panel, val + " is not a valid input in the template file, please change it"
                                                        " and reupload the file.", "Invalid Input", style=ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        return True

    ########################
    # END PARAMETER WINDOW #
    ########################


class ParamChoose(Frame):

    def __init__(self, parent: Window, name: str, params: list, x_offset=20, y_offset=20):
        """
        Constructor for the ParameterChoose window.
        :param parent: parent of this window (typically will only ever be A ParameterWindow
        :param name: name of this window
        :param params: parameters being affected
        :param x_offset: x offset of the finger
        :param y_offset: y offset of the finger
        """
        self._width = 350
        self._height = (len(params) + 6) * y_offset

        self._file_not_saved = True
        self._test_data = []

        Frame.__init__(self, parent, title=name, size=(self._width, self._height))
        self.SetMinSize(self.Size)
        self._main_panel = Panel(self)
        self.Center()  # center window on screen
        self.SetBackgroundColour("#F7CAD2")

        test_parameters = params.copy()
        self._test_type = params[0]
        del test_parameters[0]

        text_boxes = []
        iteration = 1
        for test in test_parameters:
            StaticText(self._main_panel, id=-1, label=test, pos=(x_offset, y_offset * iteration))
            text_boxes.append(TextCtrl(self._main_panel, id=-1, size=(x_offset * 4, y_offset),
                                       pos=(self._width - x_offset * 5, y_offset * iteration)))
            iteration += 1

        btn_w = 80
        btn = Button(self._main_panel, id=-1, label="Confirm", size=(btn_w, 40),
                     pos=(self._width / 2 - btn_w / 2, (len(params) + 1) * y_offset))
        btn.Bind(EVT_BUTTON, lambda e: self.get_textbox_data(e, text_boxes))

        self.Bind(EVT_CLOSE, self.on_close)  # bind closing the window to close method
        self.Show(True)

    def get_textbox_data(self, e, text_boxes: list):
        """
        reads all textbox data and runs the on_close method
        :param e: event causing this method to run
        :param text_boxes: text boxes to be read
        :return: N/A
        """
        ret_data = [self._test_type]  # initialize list with the first element being the type of test
        wrong_val = None  # initialize wrong val for messageDialog in case of bad input
        # iterate over each textbox and append the data if it is digit
        try:
            for box in text_boxes:
                wrong_val = box.GetValue()
                ret_data.append(float(box.GetValue()))
        except ValueError:
            dlg = MessageDialog(self._main_panel, "How do you expect to run a test with the parameter:\n"
                                + wrong_val, "Invalid Input", style=ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        self._test_data = ret_data
        self.on_close(None)

    def on_close(self, e):
        """
        is called when the window closes.
        Does a pubsub sendMessage to give data to the ParameterWindow
        :param e: event causing this to occur
        :return: None
        """
        # PUBSUB:
        if len(self._test_data) > 2:
            pub.sendMessage("parameter_exchange", msg=self._test_data)
        self.Destroy()

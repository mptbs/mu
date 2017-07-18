"""
Copyright (c) 2015-2016 Nicholas H.Tollervey and others (see the AUTHORS file).

Based upon work done for Puppy IDE by Dan Pope, Nicholas Tollervey and Damien
George.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import os.path
import sys
import io
import re
import json
import logging
import tempfile
import platform
import webbrowser
from PyQt5.QtWidgets import QMessageBox
from pyflakes.api import check
# Currently there is no pycodestyle deb packages, so fallback to old name
try:  # pragma: no cover
    from pycodestyle import StyleGuide, Checker
except ImportError:  # pragma: no cover
    from pep8 import StyleGuide, Checker
from mu.contrib import appdirs
from mu.contrib.atomicfile import open_atomic
from mu import __version__


#: The user's home directory.
HOME_DIRECTORY = os.path.expanduser('~')
# Name of the directory within the home folder to use by default
WORKSPACE_NAME = 'mu_code'
#: The default directory for application data (i.e., configuration).
DATA_DIR = appdirs.user_data_dir(appname='mu', appauthor='python')
#: The default directory for application logs.
LOG_DIR = appdirs.user_log_dir(appname='mu', appauthor='python')
#: The path to the log file for the application.
LOG_FILE = os.path.join(LOG_DIR, 'mu.log')
#: Regex to match pycodestyle (PEP8) output.
STYLE_REGEX = re.compile(r'.*:(\d+):(\d+):\s+(.*)')
#: Regex to match flake8 output.
FLAKE_REGEX = re.compile(r'.*:(\d+):\s+(.*)')
#: Regex to match false positive flake errors if microbit.* is expanded.
EXPAND_FALSE_POSITIVE = re.compile(r"^'microbit\.(\w+)' imported but unused$")
#: The text to which "from microbit import *" should be expanded.
EXPANDED_IMPORT = ("from microbit import pin15, pin2, pin0, pin1, "
                   " pin3, pin6, pin4, i2c, pin5, pin7, pin8, Image, "
                   "pin9, pin14, pin16, reset, pin19, temperature, "
                   "sleep, pin20, button_a, button_b, running_time, "
                   "accelerometer, display, uart, spi, panic, pin13, "
                   "pin12, pin11, pin10, compass")


logger = logging.getLogger(__name__)


def get_settings_path():
    """
    The settings file default location is the application data directory.
    However, a settings file in  the same directory than the application itself
    takes preference.
    """
    settings_filename = 'settings.json'
    # App location depends on being interpreted by normal Python or bundled
    app_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    app_dir = os.path.dirname(os.path.abspath(app_path))
    # The os x bundled application is placed 3 levels deep in the .app folder
    if platform.system() == 'Darwin' and getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(app_dir)))
    settings_dir = os.path.join(app_dir, settings_filename)
    if not os.path.exists(settings_dir):
        settings_dir = os.path.join(DATA_DIR, settings_filename)
        if not os.path.exists(settings_dir):
            try:
                with open(settings_dir, 'w') as f:
                    logger.debug('Creating settings file: {}'.format(
                                 settings_dir))
                    json.dump({}, f)
            except FileNotFoundError:
                logger.error('Unable to create settings file: {}'.format(
                             settings_dir))
    return settings_dir


def check_flake(filename, code):
    """
    Given a filename and some code to be checked, uses the PyFlakesmodule to
    return a dictionary describing issues of code quality per line. See:

    https://github.com/PyCQA/pyflakes
    """
    import_all = "from microbit import *" in code
    if import_all:
        # Massage code so "from microbit import *" is expanded so the symbols
        # are known to flake.
        code = code.replace("from microbit import *", EXPANDED_IMPORT)
    reporter = MuFlakeCodeReporter()
    check(code, filename, reporter)
    feedback = {}
    for log in reporter.log:
        if import_all:
            # Guard to stop unwanted "microbit.* imported but unused" messages.
            message = log['message']
            if EXPAND_FALSE_POSITIVE.match(message):
                continue
        if log['line_no'] not in feedback:
            feedback[log['line_no']] = []
        feedback[log['line_no']].append(log)
    return feedback


def check_pycodestyle(code):
    """
    Given some code, uses the PyCodeStyle module (was PEP8) to return a list
    of items describing issues of coding style. See:

    https://pycodestyle.readthedocs.io/en/latest/intro.html
    """
    # PyCodeStyle reads input from files, so make a temporary file containing
    # the code.
    code_fd, code_filename = tempfile.mkstemp()
    os.close(code_fd)
    with open_atomic(code_filename, 'w', newline='') as code_file:
        code_file.write(code)
    # Configure which PEP8 rules to ignore.
    style = StyleGuide(parse_argv=False, config_file=False)
    checker = Checker(code_filename, options=style.options)
    # Re-route stdout to a temporary buffer to be parsed below.
    temp_out = io.StringIO()
    sys.stdout = temp_out
    # Check the code.
    checker.check_all()
    # Put stdout back and read the content of the buffer. Remove the temporary
    # file created at the start.
    sys.stdout = sys.__stdout__
    temp_out.seek(0)
    results = temp_out.read()
    temp_out.close()
    code_file.close()
    os.remove(code_filename)
    # Parse the output from the tool into a dictionary of structured data.
    style_feedback = {}
    for result in results.split('\n'):
        matcher = STYLE_REGEX.match(result)
        if matcher:
            line_no, col, msg = matcher.groups()
            line_no = int(line_no) - 1
            code, description = msg.split(' ', 1)
            if code == 'E303':
                description += ' above this line'
            if line_no not in style_feedback:
                style_feedback[line_no] = []
            style_feedback[line_no].append({
                'line_no': line_no,
                'column': int(col) - 1,
                'message': description.capitalize(),
                'code': code,
            })
    return style_feedback


class MuFlakeCodeReporter:
    """
    The class instantiates a reporter that creates structured data about
    code quality for Mu. Used by the PyFlakes module.
    """

    def __init__(self):
        """
        Set up the reporter object to be used to report PyFlake's results.
        """
        self.log = []

    def unexpectedError(self, filename, message):
        """
        Called if an unexpected error occured while trying to process the file
        called filename. The message parameter contains a description of the
        problem.
        """
        self.log.append({
            'line_no': 0,
            'filename': filename,
            'message': str(message)
        })

    def syntaxError(self, filename, message, line_no, column, source):
        """
        Records a syntax error in the file called filename.

        The message argument contains an explanation of the syntax error,
        line_no indicates the line where the syntax error occurred, column
        indicates the column on which the error occurred and source is the
        source code containing the syntax error.
        """
        msg = ('Syntax error. Python cannot understand this line. Check for '
               'missing characters!')
        self.log.append({
            'message': msg,
            'line_no': int(line_no) - 1,  # Zero based counting in Mu.
            'column': column - 1,
            'source': source
        })

    def flake(self, message):
        """
        PyFlakes found something wrong with the code.
        """
        matcher = FLAKE_REGEX.match(str(message))
        if matcher:
            line_no, msg = matcher.groups()
            self.log.append({
                'line_no': int(line_no) - 1,  # Zero based counting in Mu.
                'column': 0,
                'message': msg,
            })
        else:
            self.log.append({
                'line_no': 0,
                'column': 0,
                'message': str(message),
            })


class REPL:
    """
    Read, Evaluate, Print, Loop.

    Represents the REPL. Since the logic for the REPL is simply a USB/serial
    based widget this class only contains a reference to the associated port.
    """

    def __init__(self, port):
        if os.name == 'posix':
            # If we're on Linux or OSX reference the port is like this...
            self.port = "/dev/{}".format(port)
        elif os.name == 'nt':
            # On Windows simply return the port (e.g. COM0).
            self.port = port
        else:
            # No idea how to deal with other OS's so fail.
            raise NotImplementedError('OS not supported.')
        logger.info('Created new REPL object with port: {}'.format(self.port))


class Editor:
    """
    Application logic for the editor itself.
    """

    def __init__(self, view, status_bar=None):
        logger.info('Setting up editor.')
        self._view = view
        self._status_bar = status_bar
        self.fs = None
        self.theme = 'day'
        self.mode = 'python'
        self.modes = {}  # See set_modes.
        self.user_defined_microbit_path = None
        if not os.path.exists(DATA_DIR):
            logger.debug('Creating directory: {}'.format(DATA_DIR))
            os.makedirs(DATA_DIR)
        logger.info('Settings path: {}'.format(get_settings_path()))
        logger.info('Log directory: {}'.format(LOG_DIR))
        logger.info('Data directory: {}'.format(DATA_DIR))

    def set_modes(self, modes):
        """
        Define the available modes.
        """
        self.modes = modes
        logger.info('Available modes: {}'.format(', '.join(self.modes.keys())))
        # Ensure there is a workspace directory.
        wd = self.modes['python'].workspace_dir()
        if not os.path.exists(wd):
            logger.debug('Creating directory: {}'.format(wd))
            os.makedirs(wd)

    def restore_session(self, passed_filename=None):
        """
        Attempts to recreate the tab state from the last time the editor was
        run.
        """
        settings_path = get_settings_path()
        self.change_mode(self.mode)
        with open(settings_path) as f:
            try:
                old_session = json.load(f)
            except ValueError:
                logger.error('Settings file {} could not be parsed.'.format(
                             settings_path))
            else:
                logger.info('Restoring session from: {}'.format(settings_path))
                logger.debug(old_session)
                if 'theme' in old_session:
                    self.theme = old_session['theme']
                if 'mode' in old_session:
                    self.mode = old_session['mode']
                if 'paths' in old_session:
                    for path in old_session['paths']:
                        # if the os passed in a file, defer loading it now
                        if passed_filename and path in passed_filename:
                            continue
                        self.direct_load(path)
                    logger.info('Loaded files.')
        # handle os passed file last,
        # so it will not be focused over by another tab
        if passed_filename:
            logger.info('Passed-in filename: {}'.format(passed_filename))
            self.direct_load(passed_filename)
        if not self._view.tab_count:
            py = 'from microbit import *{}{}# Write your code here :-)'.format(
                os.linesep, os.linesep)
            self._view.add_tab(None, py)
            logger.info('Starting with blank file.')
        self.change_mode(self.mode)
        self._view.set_theme(self.theme)

    def toggle_theme(self):
        """
        Switches between themes (night or day).
        """
        if self.theme == 'day':
            self.theme = 'night'
        else:
            self.theme = 'day'
        logger.info('Toggle theme to: {}'.format(self.theme))
        self._view.set_theme(self.theme)

    def new(self):
        """
        Adds a new tab to the editor.
        """
        logger.info('Added a new tab.')
        self._view.add_tab(None, '')

    def _load(self, path):
        logger.info('Loading script from: {}'.format(path))
        # see if file is open first
        for widget in self._view.widgets:
            if widget.path is None:  # this widget is an unsaved buffer
                continue
            if path in widget.path:
                logger.info('Script already open.')
                self._view.show_message('The file "{}" is already open'.format(
                                        os.path.basename(path)))
                self._view.focus_tab(widget)
                return
        try:
            if path.endswith('.py'):
                # Open the file, read the textual content and set the name as
                # the path to the file.
                with open(path, newline='') as f:
                    text = f.read()
                name = path
            else:
                # Open the hex, extract the Python script therein and set the
                # name to None, thus forcing the user to work out what to name
                # the recovered script.
                with open(path, newline='') as f:
                    text = uflash.extract_script(f.read())
                name = None
        except FileNotFoundError:
            logger.warning('could not load {}'.format(path))
        else:
            logger.debug(text)
            self._view.add_tab(name, text)

    def load(self):
        """
        Loads a Python file from the file system or extracts a Python script
        from a hex file.
        """
        path = self._view.get_load_path(self.modes[self.mode].workspace_dir())
        self._load(path)

    def direct_load(self, path):
        """ for loading files passed from command line or the OS launch"""
        self._load(path)

    def save(self):
        """
        Save the content of the currently active editor tab.
        """
        tab = self._view.current_tab
        if tab is None:
            # There is no active text editor so abort.
            return
        if tab.path is None:
            # Unsaved file.
            workspace = self.modes[self.mode].workspace_dir()
            tab.path = self._view.get_save_path(workspace)
        if tab.path:
            # The user specified a path to a file.
            if not os.path.basename(tab.path).endswith('.py'):
                # No extension given, default to .py
                tab.path += '.py'
            try:
                with open_atomic(tab.path, 'w', newline='') as f:
                    logger.info('Saving script to: {}'.format(tab.path))
                    logger.debug(tab.text())
                    f.write(tab.text())
                tab.setModified(False)
            except OSError as e:
                logger.error(e)
                message = 'Could not save file.'
                information = ("Error saving file to disk. Ensure you have "
                               "permission to write the file and "
                               "sufficient disk space.")
                self._view.show_message(message, information)
        else:
            # The user cancelled the filename selection.
            tab.path = None

    def zoom_in(self):
        """
        Make the editor's text bigger
        """
        logger.info('Zoom in')
        self._view.zoom_in()

    def zoom_out(self):
        """
        Make the editor's text smaller.
        """
        logger.info('Zoom out')
        self._view.zoom_out()

    def check_code(self):
        """
        Uses PyFlakes and PyCodeStyle to gather information about potential
        problems with the code in the current tab.
        """
        logger.info('Checking code.')
        self._view.reset_annotations()
        tab = self._view.current_tab
        if tab is None:
            # There is no active text editor so abort.
            return
        filename = tab.path if tab.path else 'untitled'
        flake = check_flake(filename, tab.text())
        if flake:
            logger.info(flake)
            self._view.annotate_code(flake, 'error')
        pep8 = check_pycodestyle(tab.text())
        if pep8:
            logger.info(pep8)
            self._view.annotate_code(pep8, 'style')

    def show_help(self):
        """
        Display browser based help about Mu.
        """
        logger.info('Showing help.')
        webbrowser.open_new('http://codewith.mu/help/{}'.format(__version__))

    def quit(self, *args, **kwargs):
        """
        Exit the application.
        """
        if self._view.modified:
            # Alert the user to handle unsaved work.
            msg = ('There is un-saved work, exiting the application will'
                   ' cause you to lose it.')
            result = self._view.show_confirmation(msg)
            if result == QMessageBox.Cancel:
                if args and hasattr(args[0], 'ignore'):
                    # The function is handling an event, so ignore it.
                    args[0].ignore()
                return
        paths = []
        for widget in self._view.widgets:
            if widget.path:
                paths.append(widget.path)
        session = {
            'theme': self.theme,
            'mode': self.mode,
            'paths': paths,
            'workspace': self.modes[self.mode].workspace_dir(),
            'microbit_runtime_hex': self.modes['microbit'].get_hex_path()
        }
        logger.debug(session)
        settings_path = get_settings_path()
        with open(settings_path, 'w') as out:
            logger.debug('Session: {}'.format(session))
            logger.debug('Saving session to: {}'.format(settings_path))
            json.dump(session, out, indent=2)
        logger.info('Quitting.\n\n')
        sys.exit(0)

    def show_logs(self, event):
        """
        Cause the editor's logs to be displayed to the user to help with ease
        of bug reporting.
        """
        logger.info('Showing logs from {}'.format(LOG_FILE))
        with open(LOG_FILE, 'r') as logfile:
            self._view.show_logs(logfile.read())

    def select_mode(self, event):
        """
        Select the mode that editor is supposed to be in.
        """
        logger.info('Showing available modes: {}'.format(self.modes.keys()))
        new_mode = self._view.select_mode(self.modes, self.mode)
        if new_mode and new_mode is not self.mode:
            self.mode = new_mode
            self.change_mode(self.mode)

    def change_mode(self, mode):
        """
        Given the name of a mode, will make the necessary changes to put the
        editor into the new mode.
        """
        # Remove the old mode's REPL.
        self._view.remove_repl()
        # Update buttons.
        self._view.change_mode(self.modes[mode])
        button_bar = self._view.button_bar
        button_bar.connect("new", self.new, "Ctrl+N")
        button_bar.connect("load", self.load, "Ctrl+O")
        button_bar.connect("save", self.save, "Ctrl+S")
        for action in self.modes[mode].actions():
            button_bar.connect(action['name'], action['handler'])
        button_bar.connect("zoom-in", self.zoom_in)
        button_bar.connect("zoom-out", self.zoom_out)
        button_bar.connect("theme", self.toggle_theme)
        button_bar.connect("check", self.check_code)
        button_bar.connect("help", self.show_help)
        button_bar.connect("quit", self.quit)
        self._view.status_bar.set_mode(mode)
        # Update references to default file locations.
        logger.info('Workspace directory: {}'.format(
            self.modes[mode].workspace_dir()))

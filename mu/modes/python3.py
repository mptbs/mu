"""
Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

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
import logging
from mu.modes.base import BaseMode
from qtconsole.inprocess import QtInProcessKernelManager


logger = logging.getLogger(__name__)


class PythonMode(BaseMode):
    """
    Represents the functionality required by the Python 3 mode.
    """

    name = 'Python 3'
    description = 'Create code using standard Python 3.'
    icon = 'python'
    debugger = True

    def actions(self):
        """
        Return an ordered list of actions provided by this module. An action
        is a name (also used to identify the icon) , description, and handler.
        """
        return [
            {
                'name': 'run',
                'description': 'Run your Python script.',
                'handler': self.run,
            },
            {
                'name': 'repl',
                'description': 'Use the REPL for live coding.',
                'handler': self.toggle_repl,
            },
        ]

    def apis(self):
        """
        Return a list of API specifications to be used by auto-suggest and call
        tips.
        """
        return NotImplemented

    def run(self, event):
        """
        Run the current script
        """
        logger.info('Running script.')
        # Grab the Python file.
        tab = self.view.current_tab
        if tab is None:
            # There is no active text editor.
            return
        if tab.path is None:
            # Unsaved file.
            self.editor.save()
        if tab.path:
            python_script = tab.text().encode('utf-8')
            logger.debug('Python script:')
            logger.debug(python_script)
            self.runner = QtInProcessKernelManager()
            self.runner.start_kernel(show_banner=False)
            self.view.add_python3_runner(self.runner, tab.path, self.workspace_dir())

    def toggle_repl(self, event):
        """
        Toggles the REPL on and off
        """
        if self.repl is None:
            self.add_repl()
            logger.info('Toggle REPL on.')
        else:
            self.remove_repl()
            logger.info('Toggle REPL off.')

    def add_repl(self,):
        """
        Create a new Jupyter REPL session.
        """
        self.repl = QtInProcessKernelManager()
        self.repl.start_kernel(show_banner=False)
        self.view.add_jupyter_repl(self.repl)

    def remove_repl(self):
        """
        Remove the Jupyter REPL session.
        """
        if self.repl is None:
            raise RuntimeError('REPL not running.')
        self.view.remove_repl()
        self.repl = None

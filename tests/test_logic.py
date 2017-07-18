# -*- coding: utf-8 -*-
"""
Tests for the Editor and REPL logic.
"""
import sys
import os.path
import json
import pytest
import mu.logic
from PyQt5.QtWidgets import QMessageBox
from unittest import mock
from mu import __version__


SESSION = json.dumps({
    'theme': 'night',
    'mode': 'python',
    'paths': [
        'path/foo.py',
        'path/bar.py',
    ],
})


def test_CONSTANTS():
    """
    Ensure the expected constants exist.
    """
    assert mu.logic.HOME_DIRECTORY
    assert mu.logic.DATA_DIR
    assert mu.logic.WORKSPACE_NAME


def test_get_settings_app_path():
    """
    Find a settings file in the application location when run using Python.
    """
    fake_app_path = os.path.dirname(__file__)
    fake_app_script = os.path.join(fake_app_path, 'run.py')
    wrong_fake_path = 'wrong/path/to/executable'
    fake_local_settings = os.path.join(fake_app_path, 'settings.json')
    with mock.patch.object(sys, 'executable', wrong_fake_path), \
            mock.patch.object(sys, 'argv', [fake_app_script]):
        assert mu.logic.get_settings_path() == fake_local_settings


def test_get_settings_app_path_frozen():
    """
    Find a settings file in the application location when it has been frozen
    using PyInstaller.
    """
    fake_app_path = os.path.dirname(__file__)
    fake_app_script = os.path.join(fake_app_path, 'mu.exe')
    wrong_fake_path = 'wrong/path/to/executable'
    fake_local_settings = os.path.join(fake_app_path, 'settings.json')
    with mock.patch.object(sys, 'frozen', create=True, return_value=True), \
            mock.patch('platform.system', return_value='not_Darwin'), \
            mock.patch.object(sys, 'executable', fake_app_script), \
            mock.patch.object(sys, 'argv', [wrong_fake_path]):
        assert mu.logic.get_settings_path() == fake_local_settings


def test_get_settings_app_path_frozen_osx():
    """
    Find a settings file in the application location when it has been frozen
    using PyInstaller on macOS (as the path is different in the app bundle).
    """
    fake_app_path = os.path.join(os.path.dirname(__file__), 'a', 'b', 'c')
    fake_app_script = os.path.join(fake_app_path, 'mu.exe')
    wrong_fake_path = 'wrong/path/to/executable'
    fake_local_settings = os.path.abspath(os.path.join(
        fake_app_path, '..', '..', '..', 'settings.json'))
    with mock.patch.object(sys, 'frozen', create=True, return_value=True), \
            mock.patch('platform.system', return_value='Darwin'), \
            mock.patch.object(sys, 'executable', fake_app_script), \
            mock.patch.object(sys, 'argv', [wrong_fake_path]):
        assert mu.logic.get_settings_path() == fake_local_settings


def test_get_settings_data_path():
    """
    Find a settings file in the data location.
    """
    mock_open = mock.mock_open()
    mock_exists = mock.MagicMock()
    mock_exists.side_effect = [False, True]
    mock_json_dump = mock.MagicMock()
    with mock.patch('os.path.exists', mock_exists), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('json.dump', mock_json_dump), \
            mock.patch('mu.logic.DATA_DIR', 'fake_path'):
        assert mu.logic.get_settings_path() == os.path.join(
            'fake_path', 'settings.json')
    assert not mock_json_dump.called


def test_get_settings_no_files():
    """
    No settings files found, so create one.
    """
    mock_open = mock.mock_open()
    mock_json_dump = mock.MagicMock()
    with mock.patch('os.path.exists', return_value=False), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('json.dump', mock_json_dump), \
            mock.patch('mu.logic.DATA_DIR', 'fake_path'):
        assert mu.logic.get_settings_path() == os.path.join(
            'fake_path', 'settings.json')
    assert mock_json_dump.call_count == 1


def test_get_settings_no_files_cannot_create():
    """
    No settings files found, attempting to create one causes Mu to log and
    make do.
    """
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__.side_effect = FileNotFoundError('Bang')
    mock_open.return_value.__exit__ = mock.Mock()
    mock_json_dump = mock.MagicMock()
    with mock.patch('os.path.exists', return_value=False), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('json.dump', mock_json_dump), \
            mock.patch('mu.logic.DATA_DIR', 'fake_path'), \
            mock.patch('mu.logic.logger', return_value=None) as logger:
        mu.logic.get_settings_path()
        msg = 'Unable to create settings file: ' \
              'fake_path{}settings.json'.format(os.path.sep)
        logger.error.assert_called_once_with(msg)


def test_get_workspace_valid():
    """
    Return settings file workspace value.
    """
    # read from our demo settings.json
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settings.json'), \
            mock.patch('os.path.isdir', return_value=True):
        assert mu.logic.get_workspace_dir() == '/home/foo/mycode'


def test_get_workspace_not_present():
    """
    No workspace key in settings file, return default folder.
    """
    default_workspace = os.path.join(mu.logic.HOME_DIRECTORY,
                                     mu.logic.WORKSPACE_NAME)
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settingswithoutworkspace.json'):
        assert mu.logic.get_workspace_dir() == default_workspace


def test_get_workspace_invalid_value():
    """
    Invalid workspace key in settings file, return default folder.
    """
    default_workspace = os.path.join(mu.logic.HOME_DIRECTORY,
                                     mu.logic.WORKSPACE_NAME)
    # read from our demo settings.json
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settings.json'), \
            mock.patch('os.path.isdir', return_value=False), \
            mock.patch('mu.logic.logger', return_value=None) as logger:
        assert mu.logic.get_workspace_dir() == default_workspace
        assert logger.error.call_count == 1


def test_get_workspace_invalid_json():
    """
    Invalid workspace key in settings file, return default folder.
    """
    default_workspace = os.path.join(mu.logic.HOME_DIRECTORY,
                                     mu.logic.WORKSPACE_NAME)
    mock_open = mock.mock_open(read_data='{"workspace": invalid}')
    with mock.patch('mu.logic.get_settings_path', return_value='a.json'), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('mu.logic.logger', return_value=None) as logger:
        assert mu.logic.get_workspace_dir() == default_workspace
        assert logger.error.call_count == 1


def test_get_workspace_no_settings_file():
    """
    Invalid settings file, return default folder.
    """
    default_workspace = os.path.join(mu.logic.HOME_DIRECTORY,
                                     mu.logic.WORKSPACE_NAME)
    mock_open = mock.MagicMock(side_effect=FileNotFoundError())
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settings.json'), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('mu.logic.logger', return_value=None) as logger:
        assert mu.logic.get_workspace_dir() == default_workspace
        assert logger.error.call_count == 1


def test_check_flake():
    """
    Ensure the check_flake method calls PyFlakes with the expected code
    reporter.
    """
    mock_r = mock.MagicMock()
    mock_r.log = [{'line_no': 2, 'column': 0, 'message': 'b'}]
    with mock.patch('mu.logic.MuFlakeCodeReporter', return_value=mock_r), \
            mock.patch('mu.logic.check', return_value=None) as mock_check:
        result = mu.logic.check_flake('foo.py', 'some code')
        assert result == {2: mock_r.log}
        mock_check.assert_called_once_with('some code', 'foo.py', mock_r)


def test_check_flake_needing_expansion():
    """
    Ensure the check_flake method calls PyFlakes with the expected code
    reporter.
    """
    mock_r = mock.MagicMock()
    msg = "'microbit.foo' imported but unused"
    mock_r.log = [{'line_no': 2, 'column': 0, 'message': msg}]
    with mock.patch('mu.logic.MuFlakeCodeReporter', return_value=mock_r), \
            mock.patch('mu.logic.check', return_value=None) as mock_check:
        code = 'from microbit import *'
        result = mu.logic.check_flake('foo.py', code)
        assert result == {}
        mock_check.assert_called_once_with(mu.logic.EXPANDED_IMPORT, 'foo.py',
                                           mock_r)


def test_check_pycodestyle():
    """
    Ensure the expected result if generated from the PEP8 style validator.
    """
    code = "import foo\n\n\n\n\n\ndef bar():\n    pass\n"  # Generate E303
    result = mu.logic.check_pycodestyle(code)
    assert len(result) == 1
    assert result[6][0]['line_no'] == 6
    assert result[6][0]['column'] == 0
    assert ' above this line' in result[6][0]['message']
    assert result[6][0]['code'] == 'E303'


def test_MuFlakeCodeReporter_init():
    """
    Check state is set up as expected.
    """
    r = mu.logic.MuFlakeCodeReporter()
    assert r.log == []


def test_MuFlakeCodeReporter_unexpected_error():
    """
    Check the reporter handles unexpected errors.
    """
    r = mu.logic.MuFlakeCodeReporter()
    r.unexpectedError('foo.py', 'Nobody expects the Spanish Inquisition!')
    assert len(r.log) == 1
    assert r.log[0]['line_no'] == 0
    assert r.log[0]['filename'] == 'foo.py'
    assert r.log[0]['message'] == 'Nobody expects the Spanish Inquisition!'


def test_MuFlakeCodeReporter_syntax_error():
    """
    Check the reporter handles syntax errors in a humane and kid friendly
    manner.
    """
    msg = ('Syntax error. Python cannot understand this line. Check for '
           'missing characters!')
    r = mu.logic.MuFlakeCodeReporter()
    r.syntaxError('foo.py', 'something incomprehensible to kids', '2', 3,
                  'source')
    assert len(r.log) == 1
    assert r.log[0]['line_no'] == 1
    assert r.log[0]['message'] == msg
    assert r.log[0]['column'] == 2
    assert r.log[0]['source'] == 'source'


def test_MuFlakeCodeReporter_flake_matched():
    """
    Check the reporter handles flake (regular) errors that match the expected
    message structure.
    """
    r = mu.logic.MuFlakeCodeReporter()
    err = "foo.py:4: something went wrong"
    r.flake(err)
    assert len(r.log) == 1
    assert r.log[0]['line_no'] == 3
    assert r.log[0]['column'] == 0
    assert r.log[0]['message'] == 'something went wrong'


def test_MuFlakeCodeReporter_flake_un_matched():
    """
    Check the reporter handles flake errors that do not conform to the expected
    message structure.
    """
    r = mu.logic.MuFlakeCodeReporter()
    err = "something went wrong"
    r.flake(err)
    assert len(r.log) == 1
    assert r.log[0]['line_no'] == 0
    assert r.log[0]['column'] == 0
    assert r.log[0]['message'] == 'something went wrong'


def test_REPL_posix():
    """
    The port is set correctly in a posix environment.
    """
    with mock.patch('os.name', 'posix'):
        r = mu.logic.REPL('ttyACM0')
        assert r.port == '/dev/ttyACM0'


def test_REPL_nt():
    """
    The port is set correctly in an nt (Windows) environment.
    """
    with mock.patch('os.name', 'nt'):
        r = mu.logic.REPL('COM0')
        assert r.port == 'COM0'


def test_REPL_unsupported():
    """
    A NotImplementedError is raised on an unsupported OS.
    """
    with mock.patch('os.name', 'SPARC'):
        with pytest.raises(NotImplementedError):
            mu.logic.REPL('tty0')


def test_editor_init():
    """
    Ensure a new instance is set-up correctly and creates the required folders
    upon first start.
    """
    view = mock.MagicMock()
    # Check the editor attempts to create required directories if they don't
    # already exist.
    with mock.patch('os.path.exists', return_value=False), \
            mock.patch('os.makedirs', return_value=None) as mkd:
        e = mu.logic.Editor(view)
        assert e._view == view
        assert e.theme == 'day'
        assert mkd.call_count == 2
        assert mkd.call_args_list[0][0][0] == mu.logic.DATA_DIR
        assert mkd.call_args_list[1][0][0] == mu.logic.get_workspace_dir()


def test_editor_set_modes():
    """
    An editor should have a modes attribute.
    """
    view = mock.MagicMock()
    e = mu.logic.Editor(view)
    mock_modes = mock.MagicMock()
    e.set_modes(mock_modes)
    assert e.modes == mock_modes


def test_editor_restore_session():
    """
    A correctly specified session is restored properly.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    ed.modes = mock.MagicMock()
    mock_open = mock.mock_open(read_data=SESSION)
    with mock.patch('builtins.open', mock_open), \
            mock.patch('os.path.exists', return_value=True):
        ed.restore_session()
    assert ed.theme == 'night'
    assert mock_open.return_value.read.call_count == 3
    assert ed._view.add_tab.call_count == 2
    view.set_theme.assert_called_once_with('night')


def test_editor_restore_session_missing_files():
    """
    Missing files that were opened tabs in the previous session are safely
    ignored when attempting to restore them.
    """
    fake_settings = os.path.join(os.path.dirname(__file__), 'settings.json')
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    ed.modes = mock.MagicMock()
    get_test_settings_path = mock.MagicMock()
    get_test_settings_path.return_value = fake_settings
    with mock.patch('os.path.exists', return_value=True), \
            mock.patch('mu.logic.get_settings_path', get_test_settings_path):
        ed.restore_session()
    assert ed._view.add_tab.call_count == 0


def test_editor_restore_session_no_session_file():
    """
    If there's no prior session file (such as upon first start) then simply
    start up the editor with an empty untitled tab.
    """
    view = mock.MagicMock()
    view.tab_count = 0
    ed = mu.logic.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    ed.modes = mock.MagicMock()
    with mock.patch('os.path.exists', return_value=False):
        ed.restore_session()
    py = 'from microbit import *{}{}# Write your code here :-)'.format(
        os.linesep, os.linesep)
    ed._view.add_tab.assert_called_once_with(None, py)


def test_editor_restore_session_invalid_file():
    """
    A malformed JSON file is correctly detected and app behaves the same as if
    there was no session file.
    """
    view = mock.MagicMock()
    view.tab_count = 0
    ed = mu.logic.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    ed.modes = mock.MagicMock()
    mock_open = mock.mock_open(
        read_data='{"paths": ["path/foo.py", "path/bar.py"]}, invalid: 0}')
    with mock.patch('builtins.open', mock_open), \
            mock.patch('os.path.exists', return_value=True):
        ed.restore_session()
    py = 'from microbit import *{}{}# Write your code here :-)'.format(
        os.linesep, os.linesep)
    ed._view.add_tab.assert_called_once_with(None, py)


def test_editor_open_focus_passed_file():
    """
    A file passed in by the OS is opened
    """
    view = mock.MagicMock()
    view.tab_count = 0
    ed = mu.logic.Editor(view)
    ed.modes = mock.MagicMock()
    ed._load = mock.MagicMock()
    file_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'scripts',
        'contains_red.py'
    )
    ed.restore_session(file_path)
    ed._load.assert_called_once_with(file_path)


def test_editor_session_and_open_focus_passed_file():
    """
    A passed in file is merged with session, opened last
    so it receives focus
    It will be the middle position in the session
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.modes = mock.MagicMock()
    ed.direct_load = mock.MagicMock()
    settings = json.dumps({
        "paths": ["path/foo.py",
                  "path/bar.py"]}, )
    mock_open = mock.mock_open(read_data=settings)
    with mock.patch('builtins.open', mock_open), \
            mock.patch('os.path.exists', return_value=True):
        ed.restore_session(passed_filename='path/foo.py')

    # direct_load should be called twice (once for each path)
    assert ed.direct_load.call_count == 2
    # However, "foo.py" as the passed_filename should be direct_load-ed
    # at the end so it has focus, despite being the first file listed in
    # the restored session.
    assert ed.direct_load.call_args_list[0][0][0] == 'path/bar.py'
    assert ed.direct_load.call_args_list[1][0][0] == 'path/foo.py'


def test_flash_no_tab():
    """
    If there are no active tabs simply return.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.logic.Editor(view)
    assert ed.flash() is None


def test_flash_with_attached_device():
    """
    Ensure the expected calls are made to uFlash and a helpful status message
    is enacted.
    """
    with mock.patch('mu.logic.uflash.hexlify', return_value=''), \
            mock.patch('mu.logic.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.logic.uflash.find_microbit', return_value='bar'),\
            mock.patch('mu.logic.os.path.exists', return_value=True),\
            mock.patch('mu.logic.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.logic.Editor(view)
        ed.flash()
        assert view.show_message.call_count == 1
        hex_file_path = os.path.join('bar', 'micropython.hex')
        s.assert_called_once_with('foo', hex_file_path)


def test_flash_with_attached_device_and_custom_runtime():
    """
    Ensure the expected calls are made to uFlash and a helpful status message
    is enacted.
    """
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settingswithcustomhex.json'), \
            mock.patch('mu.logic.get_workspace_dir',
                       return_value=os.path.dirname(__file__)):
        test_flash_with_attached_device()


def test_flash_user_specified_device_path():
    """
    Ensure that if a micro:bit is not automatically found by uflash then it
    prompts the user to locate the device and, assuming a path was given,
    saves the hex in the expected location.
    """
    with mock.patch('mu.logic.uflash.hexlify', return_value=''), \
            mock.patch('mu.logic.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.logic.uflash.find_microbit', return_value=None),\
            mock.patch('mu.logic.os.path.exists', return_value=True),\
            mock.patch('mu.logic.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.get_microbit_path = mock.MagicMock(return_value='bar')
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.logic.Editor(view)
        ed.flash()
        home = mu.logic.HOME_DIRECTORY
        view.get_microbit_path.assert_called_once_with(home)
        assert view.show_message.call_count == 1
        assert ed.user_defined_microbit_path == 'bar'
        hex_file_path = os.path.join('bar', 'micropython.hex')
        s.assert_called_once_with('foo', hex_file_path)


def test_flash_existing_user_specified_device_path():
    """
    Ensure that if a micro:bit is not automatically found by uflash and the
    user has previously specified a path to the device, then the hex is saved
    in the specified location.
    """
    with mock.patch('mu.logic.uflash.hexlify', return_value=''), \
            mock.patch('mu.logic.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.logic.uflash.find_microbit', return_value=None),\
            mock.patch('mu.logic.os.path.exists', return_value=True),\
            mock.patch('mu.logic.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.get_microbit_path = mock.MagicMock(return_value='bar')
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.logic.Editor(view)
        ed.user_defined_microbit_path = 'baz'
        ed.flash()
        assert view.get_microbit_path.call_count == 0
        assert view.show_message.call_count == 1
        hex_file_path = os.path.join('baz', 'micropython.hex')
        s.assert_called_once_with('foo', hex_file_path)


def test_flash_path_specified_does_not_exist():
    """
    Ensure that if a micro:bit is not automatically found by uflash and the
    user has previously specified a path to the device, then the hex is saved
    in the specified location.
    """
    with mock.patch('mu.logic.uflash.hexlify', return_value=''), \
            mock.patch('mu.logic.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.logic.uflash.find_microbit', return_value=None),\
            mock.patch('mu.logic.os.path.exists', return_value=False),\
            mock.patch('mu.logic.os.makedirs', return_value=None), \
            mock.patch('mu.logic.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.logic.Editor(view)
        ed.user_defined_microbit_path = 'baz'
        ed.flash()
        message = 'Could not find an attached BBC micro:bit.'
        information = ("Please ensure you leave enough time for the BBC"
                       " micro:bit to be attached and configured correctly"
                       " by your computer. This may take several seconds."
                       " Alternatively, try removing and re-attaching the"
                       " device or saving your work and restarting Mu if"
                       " the device remains unfound.")
        view.show_message.assert_called_once_with(message, information)
        assert s.call_count == 0
        assert ed.user_defined_microbit_path is None


def test_flash_without_device():
    """
    If no device is found and the user doesn't provide a path then ensure a
    helpful status message is enacted.
    """
    with mock.patch('mu.logic.uflash.hexlify', return_value=''), \
            mock.patch('mu.logic.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.logic.uflash.find_microbit', return_value=None), \
            mock.patch('mu.logic.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.get_microbit_path = mock.MagicMock(return_value=None)
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.logic.Editor(view)
        ed.flash()
        message = 'Could not find an attached BBC micro:bit.'
        information = ("Please ensure you leave enough time for the BBC"
                       " micro:bit to be attached and configured correctly"
                       " by your computer. This may take several seconds."
                       " Alternatively, try removing and re-attaching the"
                       " device or saving your work and restarting Mu if"
                       " the device remains unfound.")
        view.show_message.assert_called_once_with(message, information)
        home = mu.logic.HOME_DIRECTORY
        view.get_microbit_path.assert_called_once_with(home)
        assert s.call_count == 0


def test_flash_script_too_big():
    """
    If the script in the current tab is too big, abort in the expected way.
    """
    view = mock.MagicMock()
    view.current_tab.text = mock.MagicMock(return_value='x' * 8193)
    view.current_tab.label = 'foo'
    view.show_message = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.flash()
    view.show_message.assert_called_once_with('Unable to flash "foo"',
                                              'Your script is too long!',
                                              'Warning')


def test_add_fs_no_repl():
    """
    It's possible to add the file system pane if the REPL is inactive.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.microfs.get_serial', return_value=True):
        ed.add_fs()
    workspace = mu.logic.get_workspace_dir()
    view.add_filesystem.assert_called_once_with(home=workspace)
    assert ed.fs


def test_add_fs_with_repl():
    """
    If the REPL is active, you can't add the file system pane.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.repl = True
    with mock.patch('mu.logic.microfs.get_serial', return_value=True):
        ed.add_fs()
    assert view.add_filesystem.call_count == 0


def test_add_fs_no_device():
    """
    If there's no device attached then ensure a helpful message is displayed.
    """
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    ex = IOError('BOOM')
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.microfs.get_serial', side_effect=ex):
        ed.add_fs()
    assert view.show_message.call_count == 1


def test_remove_fs_no_fs():
    """
    Removing a non-existent file system raises a RuntimeError.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.fs = None
    with pytest.raises(RuntimeError):
        ed.remove_fs()


def test_remove_fs():
    """
    Removing the file system results in the expected state.
    """
    view = mock.MagicMock()
    view.remove_repl = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.fs = True
    ed.remove_fs()
    assert view.remove_filesystem.call_count == 1
    assert ed.fs is None


def test_toggle_fs_on():
    """
    If the fs is off, toggle it on.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.add_fs = mock.MagicMock()
    ed.repl = None
    ed.fs = None
    ed.toggle_fs()
    assert ed.add_fs.call_count == 1


def test_toggle_fs_off():
    """
    If the fs is on, toggle if off.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.remove_fs = mock.MagicMock()
    ed.repl = None
    ed.fs = True
    ed.toggle_fs()
    assert ed.remove_fs.call_count == 1


def test_toggle_fs_with_repl():
    """
    If the REPL is active, ensure a helpful message is displayed.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.add_repl = mock.MagicMock()
    ed.repl = True
    ed.fs = None
    ed.toggle_fs()
    assert view.show_message.call_count == 1


def test_add_repl_with_fs():
    """
    Raise a RuntimeError if the file system exists to use the serial link.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.fs = True
    with pytest.raises(RuntimeError):
        ed.add_repl()


def test_toggle_repl_with_fs():
    """
    If the file system is active, show a helpful message instead.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.remove_repl = mock.MagicMock()
    ed.repl = None
    ed.fs = True
    ed.toggle_repl()
    assert view.show_message.call_count == 1


def test_toggle_theme_to_night():
    """
    The current theme is 'day' so toggle to night. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.theme = 'day'
    ed.toggle_theme()
    assert ed.theme == 'night'
    view.set_theme.assert_called_once_with(ed.theme)


def test_toggle_theme_to_day():
    """
    The current theme is 'night' so toggle to day. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.theme = 'night'
    ed.toggle_theme()
    assert ed.theme == 'day'
    view.set_theme.assert_called_once_with(ed.theme)


def test_new():
    """
    Ensure an untitled tab is added to the UI.
    """
    view = mock.MagicMock()
    view.add_tab = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.new()
    view.add_tab.assert_called_once_with(None, '')


def test_load_python_file():
    """
    If the user specifies a Python file (*.py) then ensure it's loaded and
    added as a tab.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.py')
    view.add_tab = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mock_open = mock.mock_open(read_data='PYTHON')
    mock_workspace_dir = mock.MagicMock(return_value='/foo')
    with mock.patch('mu.logic.get_workspace_dir', mock_workspace_dir), \
            mock.patch('builtins.open', mock_open):
        ed.load()
    assert view.get_load_path.call_count == 1
    view.add_tab.assert_called_once_with('foo.py', 'PYTHON')


def test_no_duplicate_load_python_file():
    """
    If the user specifies a file already loaded, ensure this is detected.
    """
    brown_script = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'scripts',
        'contains_brown.py'
    )

    editor_window = mock.MagicMock
    editor_window.show_message = mock.MagicMock()
    editor_window.focus_tab = mock.MagicMock()
    editor_window.add_tab = mock.MagicMock()

    brown_tab = mock.MagicMock()
    brown_tab.path = brown_script
    unsaved_tab = mock.MagicMock()
    unsaved_tab.path = None

    editor_window.widgets = ({unsaved_tab, brown_tab})

    editor_window.get_load_path = mock.MagicMock(return_value=brown_script)
    # Create the "editor" that'll control the "window".
    editor = mu.logic.Editor(view=editor_window)

    editor.load()
    message = 'The file "{}" is already open'.format(os.path.basename(
                                                     brown_script))
    editor_window.show_message.assert_called_once_with(message)
    editor_window.add_tab.assert_not_called()


def test_load_hex_file():
    """
    If the user specifies a hex file (*.hex) then ensure it's loaded and
    added as a tab.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.hex')
    view.add_tab = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mock_open = mock.mock_open(read_data='PYTHON')
    mock_workspace_dir = mock.MagicMock(return_value='/foo')
    hex_file = 'RECOVERED'
    with mock.patch('mu.logic.get_workspace_dir', mock_workspace_dir), \
            mock.patch('builtins.open', mock_open), \
            mock.patch('mu.logic.uflash.extract_script',
                       return_value=hex_file) as s:
        ed.load()
    assert view.get_load_path.call_count == 1
    assert s.call_count == 1
    view.add_tab.assert_called_once_with(None, 'RECOVERED')


def test_load_error():
    """
    Ensure that anything else is just ignored.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.py')
    view.add_tab = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock(side_effect=FileNotFoundError())
    mock_workspace_dir = mock.MagicMock(return_value='/foo')
    with mock.patch('mu.logic.get_workspace_dir', mock_workspace_dir), \
            mock.patch('builtins.open', mock_open):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.add_tab.call_count == 0


def test_save_no_tab():
    """
    If there's no active tab then do nothing.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed.save()
    # If the code fell through then the tab state would be modified.
    assert view.current_tab is None


def test_save_no_path():
    """
    If there's no path associated with the tab then request the user provide
    one.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = None
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock(return_value='foo.py')
    mock_open_atomic = mock.MagicMock()
    mock_open_atomic.return_value.__enter__ = lambda s: s
    mock_open_atomic.return_value.__exit__ = mock.Mock()
    mock_open_atomic.return_value.write = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.get_workspace_dir', return_value='/fake/path'), \
            mock.patch('mu.logic.open_atomic', mock_open_atomic):
        ed.save()
    assert mock_open_atomic.call_count == 1
    mock_open_atomic.assert_called_with('foo.py', 'w', newline='')
    mock_open_atomic.return_value.write.assert_called_once_with('foo')
    view.get_save_path.assert_called_once_with('/fake/path')


def test_save_no_path_no_path_given():
    """
    If there's no path associated with the tab and the user cancels providing
    one, ensure the path is correctly re-set.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = None
    view.get_save_path = mock.MagicMock(return_value='')
    ed = mu.logic.Editor(view)
    ed.save()
    # The path isn't the empty string returned from get_save_path.
    assert view.current_tab.path is None


def test_save_file_with_exception():
    """
    If the file cannot be written, return an error message.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = 'foo.py'
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.current_tab.setModified = mock.MagicMock(return_value=None)
    view.show_message = mock.MagicMock()
    mock_open_atomic = mock.MagicMock(side_effect=OSError())
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.open_atomic', mock_open_atomic):
        ed.save()
    assert view.current_tab.setModified.call_count == 0
    assert view.show_message.call_count == 1


def test_save_python_file():
    """
    If the path is a Python file (ending in *.py) then save it and reset the
    modified flag.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = 'foo.py'
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock()
    view.current_tab.setModified = mock.MagicMock(return_value=None)
    mock_open_atomic = mock.MagicMock()
    mock_open_atomic.return_value.__enter__ = lambda s: s
    mock_open_atomic.return_value.__exit__ = mock.Mock()
    mock_open_atomic.return_value.write = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.open_atomic', mock_open_atomic):
        ed.save()
    mock_open_atomic.assert_called_once_with('foo.py', 'w', newline='')
    mock_open_atomic.return_value.write.assert_called_once_with('foo')
    assert view.get_save_path.call_count == 0
    view.current_tab.setModified.assert_called_once_with(False)


def test_save_with_no_file_extension():
    """
    If the path doesn't end in *.py then append it to the filename.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = 'foo'
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock()
    mock_open_atomic = mock.MagicMock()
    mock_open_atomic.return_value.__enter__ = lambda s: s
    mock_open_atomic.return_value.__exit__ = mock.Mock()
    mock_open_atomic.return_value.write = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.open_atomic', mock_open_atomic):
        ed.save()
    mock_open_atomic.assert_called_once_with('foo.py', 'w', newline='')
    mock_open_atomic.return_value.write.assert_called_once_with('foo')
    assert view.get_save_path.call_count == 0


def test_zoom_in():
    """
    Ensure the UI layer is zoomed in.
    """
    view = mock.MagicMock()
    view.zoom_in = mock.MagicMock(return_value=None)
    ed = mu.logic.Editor(view)
    ed.zoom_in()
    assert view.zoom_in.call_count == 1


def test_zoom_out():
    """
    Ensure the UI layer is zoomed out.
    """
    view = mock.MagicMock()
    view.zoom_out = mock.MagicMock(return_value=None)
    ed = mu.logic.Editor(view)
    ed.zoom_out()
    assert view.zoom_out.call_count == 1


def test_check_code():
    """
    Checking code correctly results in something the UI layer can parse.
    """
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.path = 'foo.py'
    tab.text.return_value = 'import this\n'
    view.current_tab = tab
    flake = {2: {'line_no': 2, 'message': 'a message', }, }
    pep8 = {2: [{'line_no': 2, 'message': 'another message', }],
            3: [{'line_no': 3, 'message': 'yet another message', }]}
    with mock.patch('mu.logic.check_flake', return_value=flake), \
            mock.patch('mu.logic.check_pycodestyle', return_value=pep8):
        ed = mu.logic.Editor(view)
        ed.check_code()
        view.reset_annotations.assert_called_once_with()
        view.annotate_code.assert_has_calls([mock.call(flake, 'error'),
                                             mock.call(pep8, 'style')],
                                            any_order=True)


def test_check_code_no_tab():
    """
    Checking code when there is no tab containing code aborts the process.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed.check_code()
    assert view.annotate_code.call_count == 0


def test_show_help():
    """
    Help should attempt to open up the user's browser and point it to the
    expected help documentation.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch('mu.logic.webbrowser.open_new', return_value=None) as wb:
        ed.show_help()
        wb.assert_called_once_with('http://codewith.mu/help/{}'.format(
                                   __version__))


def test_quit_modified_cancelled_from_button():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit()
    assert view.show_confirmation.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_cancelled_from_event():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_ok():
    """
    If the user quits and there's unsaved work that's ignored then proceed to
    save the session.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 3
    assert mock_open.return_value.write.call_count > 0


def test_quit_save_tabs_with_paths():
    """
    When saving the session, ensure those tabs with associated paths are
    logged in the session file.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 3
    assert mock_open.return_value.write.call_count > 0
    recovered = ''.join([i[0][0] for i
                        in mock_open.return_value.write.call_args_list])
    session = json.loads(recovered)
    assert 'foo.py' in session['paths']


def test_quit_save_theme():
    """
    When saving the session, ensure the theme is logged in the session file.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.logic.Editor(view)
    ed.theme = 'night'
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 3
    assert mock_open.return_value.write.call_count > 0
    recovered = ''.join([i[0][0] for i
                        in mock_open.return_value.write.call_args_list])
    session = json.loads(recovered)
    assert session['theme'] == 'night'


def test_quit_calls_sys_exit():
    """
    Ensure that sys.exit(0) is called.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.logic.Editor(view)
    ed.theme = 'night'
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None) as ex, \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    ex.assert_called_once_with(0)


def test_custom_hex_read():
    """
    Test that a custom hex file path can be read
    """
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settingswithcustomhex.json'), \
            mock.patch('mu.logic.get_workspace_dir',
                       return_value=os.path.dirname(__file__)):
        assert "customhextest.hex" in mu.logic.get_runtime_hex_path()
    """
    Test that a corrupt settings file returns None for the
    runtime hex path
    """
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settingscorrupt.json'), \
            mock.patch('mu.logic.get_workspace_dir',
                       return_value=os.path.dirname(__file__)):
        assert mu.logic.get_runtime_hex_path() is None
    """
    Test that a missing settings file returns None for the
    runtime hex path
    """
    with mock.patch('mu.logic.get_settings_path',
                    return_value='tests/settingswithmissingcustomhex.json'), \
            mock.patch('mu.logic.get_workspace_dir',
                       return_value=os.path.dirname(__file__)):
        assert mu.logic.get_runtime_hex_path() is None


def test_show_logs():
    """
    Ensure the expected log file is displayed to the end user.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mock_open = mock.mock_open()
    with mock.patch('builtins.open', mock_open):
        ed.show_logs(None)
        mock_open.assert_called_once_with(mu.logic.LOG_FILE, 'r')
        assert view.show_logs.call_count == 1


def test_select_mode():
    """
    It's possible to select and update to a new mode.
    """
    view = mock.MagicMock()
    view.select_mode.return_value = 'foo'
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    ed.select_mode(None)
    assert view.select_mode.call_count == 1
    assert ed.mode == 'foo'
    ed.change_mode.assert_called_once_with('foo')


def test_change_mode():
    """
    It should be possible to change modes in the expected fashion (buttons get
    correctly connected to event handlers).
    """
    view = mock.MagicMock()
    mock_button_bar = mock.MagicMock()
    view.button_bar = mock_button_bar
    view.change_mode = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mode = mock.MagicMock()
    mode.actions.return_value = [
        {
            'name': 'name',
            'handler': 'handler',
        },
    ]
    ed.modes = {
        'python': mode,
    }
    ed.change_mode('python')
    view.change_mode.assert_called_once_with(mode)
    assert mock_button_bar.connect.call_count == 10
    view.status_bar.set_mode.assert_called_once_with('python')

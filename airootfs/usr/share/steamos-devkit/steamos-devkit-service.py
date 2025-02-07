#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIT License
#
# Copyright (c) 2022 Valve Software inc., Collabora Ltd
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from http.server import BaseHTTPRequestHandler
import configparser
import getpass
import json
import os
import platform
import socketserver
import subprocess
import tempfile
import urllib.parse

import dbus

import avahi

SERVICE_PORT = 32000
PACKAGE = "steamos-devkit-service"
DEVKIT_HOOKS_DIR = "/usr/share/steamos-devkit/hooks"
CURRENT_TXTVERS = "txtvers=1"

ENTRY_POINT = "devkit-1"
# root until config is loaded and told otherwise, etc.
ENTRY_POINT_USER = "root"
DEVICE_USERS = []
PROPERTIES = {"txtvers": 1,
              "login": ENTRY_POINT_USER,
              "settings": "",
              "devkit1": [
                  ENTRY_POINT
              ]}
HOOK_DIRS = []
USE_DEFAULT_HOOKS = True


def write_file(data: bytes) -> str:
    """ Write given bytes to a temporary file and return the filename

    Return the empty string if unable to open temp file for some reason
    """

    with tempfile.NamedTemporaryFile(mode='w', prefix='devkit-1', encoding='utf-8',
        delete=False) as file:
        file.write(data.decode())

        return file.name

    return ''


def write_key(post_body: bytes) -> str:
    """ Write key to temp file and return filename if valid

    Return the empty string if invalid
    """
    length = len(post_body)
    found_name = False

    if length >= 64 * 1024:
        print("Key length too long")
        return ''
    if not post_body.decode().startswith('ssh-rsa '):
        print("Key doesn't start with ssh-rsa ")
        return ''

    # Get to the base64 bits
    index = 8
    while index < length and post_body[index] == ' ':
        index = index + 1

    # Make sure key is base64
    body_decoded = post_body.decode()
    while index < length:
        if ((body_decoded[index] == '+') or (body_decoded[index] == '/') or
                (body_decoded[index].isdigit()) or
                (body_decoded[index].isalpha())):
            index = index + 1
            continue
        if body_decoded[index] == '=':
            index = index + 1
            if (index < length) and (body_decoded[index] == ' '):
                break
            if (index < length) and (body_decoded[index] == '='):
                index = index + 1
                if (index < length) and (body_decoded[index] == ' '):
                    break
            print("Found = but no space or = next, invalid key")
            return ''
        if body_decoded[index] == ' ':
            break

        print("Found invalid data, invalid key at "
              f"index: {index} data: {body_decoded[index]}")
        return ''

    print(f"Key is valid base64, writing to temp file index: {index}")
    while index < length:
        if body_decoded[index] == ' ':
            # it's a space, the rest is name or magic phrase, don't write to disk
            if found_name:
                print(f"Found name ending at index {index}")
                length = index
            else:
                print(f"Found name ending index {index}")
                found_name = True
        if body_decoded[index] == '\0':
            print("Found null terminator before expected")
            return ''
        if body_decoded[index] == '\n' and index != length - 1:
            print("Found newline before expected")
            return ''
        index = index + 1

    # write data to the file
    data = body_decoded[:length]
    filename = write_file(data.encode())

    if filename:
        print(f"Filename key written to: {filename}")

    return filename


def find_hook(name: str) -> str:
    """ Find a hook with the given name

    Return the path to the hook if found. '' if not found
    """
    # First see if it exists in the given paths.
    for path in HOOK_DIRS:
        test_path = os.path.join(path, name)
        if os.path.exists(test_path) and os.access(test_path, os.X_OK):
            return test_path

    if not USE_DEFAULT_HOOKS:
        print(f"Error: Unable to find hook for {name} in hook directories\n")
        return ''

    test_path = f"/etc/{PACKAGE}/hooks/{name}"
    if os.path.exists(test_path) and os.access(test_path, os.X_OK):
        return test_path

    test_path = f"{DEVKIT_HOOKS_DIR}/{name}"
    if os.path.exists(test_path) and os.access(test_path, os.X_OK):
        return test_path

    test_path = f"{DEVKIT_HOOKS_DIR}/{name}.sample"
    if os.path.exists(test_path) and os.access(test_path, os.X_OK):
        return test_path

    test_path = f"{os.path.dirname(os.path.realpath(__file__))}/../hooks/{name}"
    if os.path.exists(test_path) and os.access(test_path, os.X_OK):
        return test_path

    print(f"Error:: Unable to find hook for {name} in /etc/{PACKAGE}/hooks or {DEVKIT_HOOKS_DIR}")
    return ''


def get_machine_name() -> str:
    """ Get the machine name and return it in a string

    Use identify hook first, and if that fails just get the hostname.
    """
    machine_name = ''
    # Run devkit-1-identify hook to get hostname, otherwise use default platform.node()
    identify_hook = find_hook("devkit-1-identify")
    if identify_hook:
        # Run hook and parse machine_name out
        process = subprocess.Popen(identify_hook, shell=False, stdout=subprocess.PIPE)
        output = ''
        for line in process.stdout:
            textline = line.decode(encoding='utf-8', errors="ignore")
            output += textline
        process.wait()
        output_object = json.loads(output)
        if 'machine_name' in output_object:
            machine_name = output_object["machine_name"]

    if not machine_name:
        machine_name = platform.node()

    return machine_name


class DevkitHandler(BaseHTTPRequestHandler):
    """ Class to handle http requests on selected port for registration, getting properties.
    """
    def _send_headers(self, code, content_type):
        self.send_response(code)
        self.send_header("Content-type", content_type)
        self.end_headers()

    def do_GET(self):
        """ Handle GET requests
        """
        print(f"GET request to path {self.path} from {self.client_address[0]}")

        if self.path == "/login-name":
            self._send_headers(200, "text/plain")
            self.wfile.write(ENTRY_POINT_USER.encode())
            return

        if self.path == "/properties.json":
            self._send_headers(200, "application/json")
            self.wfile.write(json.dumps(PROPERTIES, indent=2).encode())
            return

        query = urllib.parse.parse_qs(self.path[2:])
        print(f"query is {query}")

        if len(query) > 0 and query["command"]:
            command = query["command"][0]

            if command == "ping":
                self._send_headers(200, "text/plain")
                self.wfile.write("pong\n".encode())
                return

            self._send_headers(404, "")
            return

        self._send_headers(404, "")
        self.wfile.write("Unknown request\n".encode())

    def do_POST(self):
        """ Handle POST requests
        """
        if self.path == "/register":
            from_ip = self.client_address[0]
            content_len = int(self.headers.get('Content-Length'))
            post_body = self.rfile.read(content_len)
            print(f"register request from {from_ip}")
            filename = write_key(post_body)

            if not filename:
                self._send_headers(403, "text/plain")
                self.wfile.write(json.dumps({'error':'Failed to write the ssh key'}).encode())
                return

            # Run approve script
            approve_hook = find_hook("approve-ssh-key")
            if not approve_hook:
                self._send_headers(403, "text/plain")
                self.wfile.write(json.dumps({'error':'Failed to find approve hook'}).encode())
                os.unlink(filename)
                return

            # Run hook and parse output
            approve_process = subprocess.Popen([approve_hook, filename, from_ip],
                                               shell=False,
                                               stdout=subprocess.PIPE)
            approve_output = ''
            for approve_line in approve_process.stdout:
                approve_textline = approve_line.decode(encoding='utf-8', errors="ignore")
                approve_output += approve_textline

            approve_process.wait()
            approve_object = json.loads(approve_output)
            if "error" in approve_object:
                self._send_headers(403, "text/plain")
                self.wfile.write(approve_output.encode()) # is already a json {'error':} response
                os.unlink(filename)
                return

            # Otherwise, assume it passed
            install_hook = find_hook("install-ssh-key")
            if not install_hook:
                self._send_headers(403, "text-plain")
                self.wfile.write(json.dumps({'error':'Failed to find install-ssh-key hook'}).encode())
                os.unlink(filename)
                return

            command = [install_hook, filename]
            # Append each user to command as separate arguments
            for user in DEVICE_USERS:
                command.append(user)

            install_process = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE)
            install_output = ''
            for install_line in install_process.stdout:
                install_textline = install_line.decode(encoding='utf-8', errors="ignore")
                install_output += install_textline
            install_process.wait()

            exit_code = install_process.returncode
            if exit_code != 0:
                self._send_headers(500, "text/plain")
                self.wfile.write("install-ssh-key:\n".encode())
                self.wfile.write(install_output.encode())
                os.unlink(filename)
                return

            self._send_headers(200, "text/plain")
            self.wfile.write("Registered\n".encode())
            os.unlink(filename)


class DevkitService:
    """ Class to run as service.

    Parses configuration, creates handler, registers with avahi, etc.
    """
    def __init__(self):
        global ENTRY_POINT_USER
        global DEVICE_USERS

        self.port = SERVICE_PORT
        self.name = get_machine_name()
        self.host = ""
        self.domain = ""
        self.stype = "_steamos-devkit._tcp"
        self.text = ""
        self.group = None

        config = configparser.ConfigParser()
        # Use str form to preserve case
        config.optionxform = str
        config.read(["/etc/steamos-devkit/steamos-devkit.conf",
                     "/usr/share/steamos-devkit/steamos-devkit.conf",
                     os.path.join(os.path.expanduser('~'), '.config', PACKAGE, PACKAGE + '.conf')])

        self.settings = {}
        if 'Settings' in config:
            settings = config["Settings"]
            self.settings = dict(settings)
            if 'Port' in settings:
                self.port = int(settings["Port"])

        PROPERTIES["settings"] = json.dumps(self.settings)

        # Parse users from configs
        if os.geteuid() == 0:
            # Running as root, maybe warn?
            print("Running as root, Probably shouldn't be\n")
            if 'Users' in config:
                users = config["Users"]
                if 'ShellUsers' in users:
                    DEVICE_USERS = users["ShellUsers"]
        else:
            if 'Users' in config:
                users = config["Users"]
                if 'ShellUsers' in users:
                    DEVICE_USERS = users["ShellUsers"]
            else:
                username = getpass.getuser()
                print("Username: {username}")
                DEVICE_USERS = []
                DEVICE_USERS.append(username)

        # If only one user, that's the entry point user
        # Otherwise entry_point_user needs to be root to be able to switch between users
        if len(DEVICE_USERS) == 1:
            ENTRY_POINT_USER = DEVICE_USERS[0]
            PROPERTIES["login"] = ENTRY_POINT_USER

        self.httpd = socketserver.TCPServer(("", self.port), DevkitHandler, bind_and_activate=False)
        print(f"serving at port: {self.port}")
        print(f"machine name: {self.name}")
        self.httpd.allow_reuse_address = True
        self.httpd.server_bind()
        self.httpd.server_activate()

    def publish(self):
        """ Publish ourselves on avahi mdns system as an available devkit device.
        """
        bus = dbus.SystemBus()
        self.text = [f"{CURRENT_TXTVERS}".encode(),
                     f"settings={json.dumps(self.settings)}".encode(),
                     f"login={ENTRY_POINT_USER}".encode(),
                     f"devkit1={ENTRY_POINT}".encode()
                     ]
        server = dbus.Interface(
            bus.get_object(
                avahi.DBUS_NAME,
                avahi.DBUS_PATH_SERVER),
            avahi.DBUS_INTERFACE_SERVER)

        avahi_object = dbus.Interface(
            bus.get_object(avahi.DBUS_NAME,
                           server.EntryGroupNew()),
            avahi.DBUS_INTERFACE_ENTRY_GROUP)
        avahi_object.AddService(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                                self.name, self.stype, self.domain, self.host,
                                dbus.UInt16(int(self.port)), self.text)

        avahi_object.Commit()
        self.group = avahi_object

    def unpublish(self):
        """ Remove publishing of ourselves as devkit device since we are quitting.
        """
        self.group.Reset()

    def run_server(self):
        """ Run server until keyboard interrupt or we are killed
        """
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass

        self.httpd.server_close()
        print(f"done serving at port: {self.port}")


if __name__ == "__main__":
    service = DevkitService()

    service.publish()
    service.run_server()

    service.unpublish()
